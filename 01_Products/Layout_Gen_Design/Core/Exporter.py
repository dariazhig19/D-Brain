"""
Core/Exporter.py
Exports a generated layout to a DXF file using ezdxf.
Supports both rectangular and polygon plot boundaries.
"""

import io
import ezdxf
from ezdxf import colors
from ezdxf.enums import TextEntityAlignment


# ── Layer definitions ───────────────────────────────────────────────────────
LAYERS = [
    # (name,                color_index,     linetype)
    ("SITE_BOUNDARY",       colors.WHITE,    "CONTINUOUS"),
    ("ROAD_SETBACK",        colors.RED,      "DASHED"),
    ("GATE_HOUSE",          colors.YELLOW,   "CONTINUOUS"),
    ("POWER_BLOCK",         colors.CYAN,     "CONTINUOUS"),
    ("COOLING_TOWER",       colors.GREEN,    "CONTINUOUS"),
    ("ADMIN_BUILDING",      colors.MAGENTA,  "CONTINUOUS"),
    ("GIS",                 5,               "CONTINUOUS"),   # blue (ACI 5)
    ("FLARE",               30,              "CONTINUOUS"),   # orange (ACI 30)
    ("WT_WWT",              4,               "CONTINUOUS"),   # light blue (ACI 4)
    ("WATER",               3,               "CONTINUOUS"),   # teal (ACI 3)
    ("WAREHOUSE",           colors.MAGENTA,  "CONTINUOUS"),
    ("ROAD",                colors.GRAY,     "CONTINUOUS"),
    ("PIPE_RACK",           colors.GRAY,     "DASHED"),
    ("MAIN_RACK",           colors.GRAY,     "DASHED"),
    ("UTILITY_RACK",        colors.GRAY,     "DASHED"),
    ("LABELS",              colors.WHITE,    "CONTINUOUS"),
    ("DIMENSIONS",          colors.GRAY,     "CONTINUOUS"),
]

# Map group/block names to layer names
GROUP_LAYER_MAP = {
    "Power Block":    "POWER_BLOCK",
    "Cooling Tower":  "COOLING_TOWER",
    "Admin Building": "ADMIN_BUILDING",
    "Gate House":     "GATE_HOUSE",
    "GIS":            "GIS",
    "Flare":          "FLARE",
    "WT/WWT":         "WT_WWT",
    "RAW Water Tank": "WATER",
    "Demi Water Tank":"WATER",
    "Warehouse":      "WAREHOUSE",
}

RACK_LAYER_MAP = {
    "Pipe Rack":    "PIPE_RACK",
    "Main Rack":    "MAIN_RACK",
    "Utility Rack": "UTILITY_RACK",
}


def _add_closed_polyline(msp, points, layer):
    """Draw a closed 2D polyline on the given layer."""
    msp.add_lwpolyline(points, close=True, dxfattribs={"layer": layer})


def _add_rect(msp, x, y, w, h, layer):
    """Shortcut: add a closed rectangle."""
    _add_closed_polyline(msp, [(x, y), (x+w, y), (x+w, y+h), (x, y+h)], layer)


def _add_label(msp, text, cx, cy, height, layer):
    """Add a centered text label."""
    msp.add_text(
        text,
        dxfattribs={
            "layer":  layer,
            "height": height,
            "insert": (cx, cy),
            "halign": 4,    # middle-center horizontal
            "valign": 0,
        },
    ).set_placement((cx, cy), align=TextEntityAlignment.MIDDLE_CENTER)


def merge_segments_to_paths(segments):
    """
    Given a list of segments [(p1, p2), ...],
    merge them into a list of continuous paths (each a list of points).
    """
    from collections import defaultdict
    adj = defaultdict(list)
    for p1, p2 in segments:
        p1_t = (round(p1[0], 2), round(p1[1], 2))
        p2_t = (round(p2[0], 2), round(p2[1], 2))
        if p1_t == p2_t:
            continue
        adj[p1_t].append(p2_t)
        adj[p2_t].append(p1_t)
        
    visited_edges = set()
    paths = []
    
    # 1. Start from endpoints (degree 1)
    endpoints = [v for v, neighbors in adj.items() if len(neighbors) == 1]
    for start in endpoints:
        if not adj[start]:
            continue
        curr = start
        path = [curr]
        while True:
            next_pt = None
            for nxt in adj[curr]:
                edge = (min(curr, nxt), max(curr, nxt))
                if edge not in visited_edges:
                    next_pt = nxt
                    visited_edges.add(edge)
                    break
            if next_pt is None:
                break
            curr = next_pt
            path.append(curr)
        if len(path) > 1:
            paths.append(path)
            
    # 2. Trace remaining closed loops (degree >= 2)
    for start in list(adj.keys()):
        has_unvisited = False
        for nxt in adj[start]:
            edge = (min(start, nxt), max(start, nxt))
            if edge not in visited_edges:
                has_unvisited = True
                break
        if not has_unvisited:
            continue
            
        curr = start
        path = [curr]
        while True:
            next_pt = None
            for nxt in adj[curr]:
                edge = (min(curr, nxt), max(curr, nxt))
                if edge not in visited_edges:
                    next_pt = nxt
                    visited_edges.add(edge)
                    break
            if next_pt is None:
                break
            curr = next_pt
            path.append(curr)
        if len(path) > 1:
            paths.append(path)
            
    return paths


def offset_polyline(vertices, d, closed=False):
    """
    Offset a list of vertices representing an axis-aligned polyline
    by distance d on both sides. Returns (left_polyline, right_polyline).
    Handles corners correctly using normal bisectors.
    """
    n = len(vertices)
    if n < 2:
        return list(vertices), list(vertices)
        
    left_pts = []
    right_pts = []
    
    for i in range(n):
        P_curr = vertices[i]
        
        # Determine incoming direction
        if i == 0:
            if closed:
                v_in = (P_curr[0] - vertices[-1][0], P_curr[1] - vertices[-1][1])
            else:
                v_in = None
        else:
            v_in = (P_curr[0] - vertices[i-1][0], P_curr[1] - vertices[i-1][1])
            
        # Determine outgoing direction
        if i == n - 1:
            if closed:
                v_out = (vertices[0][0] - P_curr[0], vertices[0][1] - P_curr[1])
            else:
                v_out = None
        else:
            v_out = (vertices[i+1][0] - P_curr[0], vertices[i+1][1] - P_curr[1])
            
        # Compute normal vectors
        n_in = None
        if v_in:
            len_in = (v_in[0]**2 + v_in[1]**2)**0.5
            if len_in > 0.001:
                u_in = (v_in[0]/len_in, v_in[1]/len_in)
                n_in = (-u_in[1], u_in[0])
                
        n_out = None
        if v_out:
            len_out = (v_out[0]**2 + v_out[1]**2)**0.5
            if len_out > 0.001:
                u_out = (v_out[0]/len_out, v_out[1]/len_out)
                n_out = (-u_out[1], u_out[0])
                
        # Combine normals
        if n_in and n_out:
            cross = n_in[0]*n_out[1] - n_in[1]*n_out[0]
            if abs(cross) < 0.01:
                n_comb = n_in
            else:
                # Orthogonal turn corner bisector offset vector
                n_comb = (n_in[0] + n_out[0], n_in[1] + n_out[1])
        elif n_in:
            n_comb = n_in
        elif n_out:
            n_comb = n_out
        else:
            n_comb = (0, 0)
            
        left_pts.append((P_curr[0] + d * n_comb[0], P_curr[1] + d * n_comb[1]))
        right_pts.append((P_curr[0] - d * n_comb[0], P_curr[1] - d * n_comb[1]))
        
    return left_pts, right_pts


def export_to_dxf(layout, site_width, site_length, plot=None):
    """
    Convert a layout dict to a DXF binary stream.

    Args:
        layout      : dict with keys 'groups', 'racks', 'scoring'
        site_width  : float — site width in metres
        site_length : float — site length in metres
        plot        : Plot  — optional Plot polygon object

    Returns:
        DXF content as a string, ready for st.download_button.
    """
    doc = ezdxf.new(dxfversion="R2010")
    doc.header["$INSUNITS"] = 6   # 6 = metres

    if plot is not None and not hasattr(plot, "vertices"):
        from Core.Plot import Plot
        plot = Plot(plot)

    # Register linetypes
    if "DASHED" not in doc.linetypes:
        doc.linetypes.add("DASHED", pattern=[0.5, -0.25])

    # Register layers
    for name, color, ltype in LAYERS:
        ltype_exists = ltype in doc.linetypes
        doc.layers.add(
            name,
            color=color,
            linetype=ltype if ltype_exists or ltype == "CONTINUOUS" else "CONTINUOUS",
        )

    msp = doc.modelspace()

    # ── 1. Site Boundary ────────────────────────────────────────────────────
    if plot is not None and len(plot.vertices) >= 3:
        _add_closed_polyline(msp, plot.vertices, "SITE_BOUNDARY")
        cx, cy = plot.centroid
        _add_label(msp, f"Site (Polygon Boundary)", cx, cy + (site_length / 2) + 6, 3.0, "LABELS")
    else:
        _add_rect(msp, 0, 0, site_width, site_length, "SITE_BOUNDARY")
        _add_label(msp, f"Site  {site_width:.0f} x {site_length:.0f} m",
                   site_width / 2, site_length + 6, 3.0, "LABELS")

    # ── 2. Roads (offset 4m on both sides for 8m road width) ─────────────────
    if "ring_road" in layout and layout["ring_road"]:
        l_road, r_road = offset_polyline(layout["ring_road"], d=4.0, closed=True)
        _add_closed_polyline(msp, l_road, "ROAD")
        _add_closed_polyline(msp, r_road, "ROAD")
        
    if "gate_spur" in layout and layout["gate_spur"]:
        l_gate, r_gate = offset_polyline(layout["gate_spur"], d=4.0, closed=False)
        msp.add_lwpolyline(l_gate, close=False, dxfattribs={"layer": "ROAD"})
        msp.add_lwpolyline(r_gate, close=False, dxfattribs={"layer": "ROAD"})
        
    if "ring_spur" in layout and layout["ring_spur"]:
        l_ring, r_ring = offset_polyline(layout["ring_spur"], d=4.0, closed=False)
        msp.add_lwpolyline(l_ring, close=False, dxfattribs={"layer": "ROAD"})
        msp.add_lwpolyline(r_ring, close=False, dxfattribs={"layer": "ROAD"})

    if "access_roads" in layout and layout["access_roads"]:
        for path in layout["access_roads"]:
            l_acc, r_acc = offset_polyline(path, d=4.0, closed=False)
            msp.add_lwpolyline(l_acc, close=False, dxfattribs={"layer": "ROAD"})
            msp.add_lwpolyline(r_acc, close=False, dxfattribs={"layer": "ROAD"})

    # ── 3. Building Groups ──────────────────────────────────────────────────
    for group in layout["groups"]:
        x, y = group["x"], group["y"]
        w, h = group["width"], group["height"]
        layer = GROUP_LAYER_MAP.get(group["name"], "SITE_BOUNDARY")

        # Outline
        _add_rect(msp, x, y, w, h, layer)

        # Centre cross-hair (2 short lines)
        cx, cy = x + w/2, y + h/2
        tick = min(w, h) * 0.08
        msp.add_line((cx - tick, cy), (cx + tick, cy), dxfattribs={"layer": layer})
        msp.add_line((cx, cy - tick), (cx, cy + tick), dxfattribs={"layer": layer})

        # Name label inside block
        label_height = max(1.5, min(w, h) * 0.10)
        _add_label(msp, group["name"], cx, cy, label_height, "LABELS")

        # Dimension: width annotation below
        msp.add_linear_dim(
            base=(x, y - 6),
            p1=(x, y),
            p2=(x + w, y),
            dimstyle="EZ_M_100_H25_CM",
            override={"dimtxt": 2.0},
            dxfattribs={"layer": "DIMENSIONS"},
        ).render()
        # Dimension: height annotation to the right
        msp.add_linear_dim(
            base=(x + w + 6, y),
            p1=(x + w, y),
            p2=(x + w, y + h),
            angle=90,
            dimstyle="EZ_M_100_H25_CM",
            override={"dimtxt": 2.0},
            dxfattribs={"layer": "DIMENSIONS"},
        ).render()

    # ── 4. Polyline Racks (offset 3m on both sides for 6m rack width) ────────
    for rack in layout.get("racks", []):
        layer = RACK_LAYER_MAP.get(rack["name"], "PIPE_RACK")
        paths = merge_segments_to_paths(rack.get("segments", []))
        for path in paths:
            is_closed_loop = len(path) > 2 and path[0] == path[-1]
            if is_closed_loop:
                l_rack, r_rack = offset_polyline(path[:-1], d=3.0, closed=True)
                msp.add_lwpolyline(l_rack, close=True, dxfattribs={"layer": layer})
                msp.add_lwpolyline(r_rack, close=True, dxfattribs={"layer": layer})
            else:
                l_rack, r_rack = offset_polyline(path, d=3.0, closed=False)
                msp.add_lwpolyline(l_rack, close=False, dxfattribs={"layer": layer})
                msp.add_lwpolyline(r_rack, close=False, dxfattribs={"layer": layer})

    # ── 5. Score annotation ─────────────────────────────────────────────────
    if "scoring" in layout and layout["scoring"]:
        total   = layout["scoring"]["total_penalty"]
        passing = sum(1 for r in layout["scoring"]["results"] if r["passed"])
        n_rules = len(layout["scoring"]["results"])
        score_text = f"Penalty Score: {total:,.0f} pts  |  {passing}/{n_rules} rules passing"
        # Insert score text slightly below the plot bounding box
        minx, miny, _, _ = plot.bbox if plot is not None else (0, 0, site_width, site_length)
        msp.add_text(
            score_text,
            dxfattribs={"layer": "LABELS", "height": 3.0,
                        "insert": (minx, miny - 15)},
        )

    # ── Serialise to String ─────────────────────────────────────────────────
    stream = io.StringIO()
    doc.write(stream)
    return stream.getvalue()

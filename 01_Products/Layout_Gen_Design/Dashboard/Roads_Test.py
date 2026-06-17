"""Road dashboard — Phase 06 sketch roads.

Run with:
    streamlit run 01_Products/Layout_Gen_Design/Dashboard/Roads_Test.py
"""

import streamlit as st
import sys, os, random
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

import importlib
import Core.Groups, Core.Grid, Core.Pathfind, Core.Layout06
importlib.reload(Core.Grid)
importlib.reload(Core.Pathfind)
importlib.reload(Core.Groups)
importlib.reload(Core.Layout06)

SHAPES = Core.Groups.SHAPES
generate_sketch = Core.Layout06.generate_sketch
CELL_SIZE = Core.Layout06.CELL_SIZE
ROAD_BUFFER = Core.Layout06.ROAD_BUFFER

def draw_orthogonal_line(ax, p1, p2, width, color, alpha=0.95, zorder=1.5, label="", cap_p1=True, cap_p2=True):
    x1, y1 = p1
    x2, y2 = p2
    r = width / 2
    # Draw endpoint caps only if they are not free ends
    if cap_p1:
        ax.add_patch(mpatches.Circle((x1, y1), r, facecolor=color, edgecolor='none', alpha=alpha, zorder=zorder))
    if cap_p2:
        ax.add_patch(mpatches.Circle((x2, y2), r, facecolor=color, edgecolor='none', alpha=alpha, zorder=zorder))
    if abs(y1 - y2) < 0.1: # Horizontal
        xmin = min(x1, x2)
        xmax = max(x1, x2)
        rect = mpatches.Rectangle((xmin, y1 - r), xmax - xmin, width, 
                                  facecolor=color, edgecolor='none', alpha=alpha, zorder=zorder, label=label)
        ax.add_patch(rect)
    elif abs(x1 - x2) < 0.1: # Vertical
        ymin = min(y1, y2)
        ymax = max(y1, y2)
        rect = mpatches.Rectangle((x1 - r, ymin), width, ymax - ymin, 
                                  facecolor=color, edgecolor='none', alpha=alpha, zorder=zorder, label=label)
        ax.add_patch(rect)
    else:
        ax.plot([x1, x2], [y1, y2], color=color, linewidth=width, alpha=alpha, zorder=zorder, label=label)

def draw_fillet(ax, B, u1, u2, r, R, color, alpha=0.95, zorder=1.5, bg_color='#f0f8ff'):
    # I = B - r * u1 + r * u2
    Ix = B[0] - r * u1[0] + r * u2[0]
    Iy = B[1] - r * u1[1] + r * u2[1]
    
    # Tangent points for inner arc
    t1x = Ix - R * u1[0]
    t1y = Iy - R * u1[1]
    t2x = Ix + R * u2[0]
    t2y = Iy + R * u2[1]
    
    # Center of arc
    cx = Ix - R * u1[0] + R * u2[0]
    cy = Iy - R * u1[1] + R * u2[1]
    
    import math
    # Compute angles of T1 and T2 relative to C
    theta1 = math.atan2(t1y - cy, t1x - cx)
    theta2 = math.atan2(t2y - cy, t2x - cx)
    
    # Determine the step direction
    diff = theta2 - theta1
    if diff > math.pi: diff -= 2 * math.pi
    elif diff < -math.pi: diff += 2 * math.pi
    
    # Generate points along the inner arc
    num_pts = 16
    pts_in = [(Ix, Iy)]
    for i in range(num_pts + 1):
        t = theta1 + diff * (i / num_pts)
        pts_in.append((cx + R * math.cos(t), cy + R * math.sin(t)))
        
    # Draw inner fillet (road color)
    polygon_in = mpatches.Polygon(pts_in, facecolor=color, edgecolor='none', alpha=alpha, zorder=zorder)
    ax.add_patch(polygon_in)


def draw_road_with_fillets(ax, path, width, color, fillet_radius=14.0, alpha=0.95, zorder=1.5, label="", is_closed=False, free_ends=None):
    if not path or len(path) < 2:
        return
        
    def pt_key(p):
        return (round(p[0], 3), round(p[1], 3))
        
    if is_closed and len(path) > 2 and pt_key(path[0]) == pt_key(path[-1]):
        path = list(path)[:-1]
        
    # Draw all segments
    for i in range(len(path) - 1):
        p1, p2 = path[i], path[i+1]
        k1, k2 = pt_key(p1), pt_key(p2)
        
        cap_p1 = True
        cap_p2 = True
        
        if free_ends is not None:
            if k1 in free_ends:
                cap_p1 = False
            if k2 in free_ends:
                cap_p2 = False
        else:
            if not is_closed:
                if i == 0:
                    cap_p1 = False
                if i == len(path) - 2:
                    cap_p2 = False
                    
        draw_orthogonal_line(ax, p1, p2, width, color, alpha, zorder, 
                             label if (i == 0 and label) else "", cap_p1=cap_p1, cap_p2=cap_p2)
                             
    if is_closed:
        p_last, p_first = path[-1], path[0]
        k_last, k_first = pt_key(p_last), pt_key(p_first)
        cap_p1 = True
        cap_p2 = True
        if free_ends is not None:
            if k_last in free_ends: cap_p1 = False
            if k_first in free_ends: cap_p2 = False
        draw_orthogonal_line(ax, p_last, p_first, width, color, alpha, zorder, cap_p1=cap_p1, cap_p2=cap_p2)
        
    # Now draw fillets at turns
    import math
    r = width / 2
    
    # Build list of points to process turns
    if is_closed:
        # Loop closed, so pad start with last element and end with first two elements
        padded = [path[-1]] + list(path) + [path[0], path[1]]
    else:
        padded = list(path)
        
    for i in range(1, len(padded) - 1):
        p_prev = padded[i-1]
        p_curr = padded[i]
        p_next = padded[i+1]
        
        # Calculate unit vectors
        v1 = (p_curr[0] - p_prev[0], p_curr[1] - p_prev[1])
        len1 = math.hypot(*v1)
        if len1 < 0.1: continue
        u1 = (v1[0] / len1, v1[1] / len1)
        
        v2 = (p_next[0] - p_curr[0], p_next[1] - p_curr[1])
        len2 = math.hypot(*v2)
        if len2 < 0.1: continue
        u2 = (v2[0] / len2, v2[1] / len2)
        
        # Check if it's a 90 degree turn (cross product close to 1 or -1)
        cross = u1[0]*u2[1] - u1[1]*u2[0]
        if abs(abs(cross) - 1.0) < 0.1:
            R = min(fillet_radius, len1 / 2, len2 / 2)
            if R < 0.5: continue
            draw_fillet(ax, p_curr, u1, u2, r, R, color, alpha, zorder)

def draw_network_with_fillets(ax, segments, width, color, fillet_radius=5.0, alpha=0.95, zorder=1.5, label=""):
    if not segments:
        return
        
    import collections
    adj = collections.defaultdict(list)
    
    def pt_key(p):
        return (round(p[0], 3), round(p[1], 3))
        
    key_to_pt = {}
    
    for seg in segments:
        if not seg or len(seg) < 2:
            continue
        p1, p2 = seg[0], seg[1]
        k1, k2 = pt_key(p1), pt_key(p2)
        if k1 == k2:
            continue
        adj[k1].append(k2)
        adj[k2].append(k1)
        key_to_pt[k1] = p1
        key_to_pt[k2] = p2
        
    # Find all free ends (degree 1 in the network)
    free_ends = {k for k, neighbors in adj.items() if len(neighbors) == 1}
    
    visited_edges = set()
    
    def make_edge(k1, k2):
        return frozenset({k1, k2})
        
    paths = []
    
    # 1. Trace from nodes with degree != 2
    for start_key in list(adj.keys()):
        deg = len(adj[start_key])
        if deg == 2:
            continue
        for nbr_key in adj[start_key]:
            edge = make_edge(start_key, nbr_key)
            if edge in visited_edges:
                continue
            path = [start_key, nbr_key]
            visited_edges.add(edge)
            
            curr = nbr_key
            prev = start_key
            while len(adj[curr]) == 2:
                nbrs = adj[curr]
                next_key = nbrs[0] if nbrs[1] == prev else nbrs[1]
                next_edge = make_edge(curr, next_key)
                if next_edge in visited_edges:
                    break
                path.append(next_key)
                visited_edges.add(next_edge)
                prev = curr
                curr = next_key
            paths.append([key_to_pt[k] for k in path])
            
    # 2. Trace remaining closed loops
    for start_key in list(adj.keys()):
        for nbr_key in adj[start_key]:
            edge = make_edge(start_key, nbr_key)
            if edge in visited_edges:
                continue
            path = [start_key, nbr_key]
            visited_edges.add(edge)
            curr = nbr_key
            prev = start_key
            while len(adj[curr]) == 2:
                nbrs = adj[curr]
                next_key = nbrs[0] if nbrs[1] == prev else nbrs[1]
                next_edge = make_edge(curr, next_key)
                if next_edge in visited_edges:
                    break
                path.append(next_key)
                visited_edges.add(next_edge)
                prev = curr
                curr = next_key
            paths.append([key_to_pt[k] for k in path])
            
    # Draw all traced paths
    for i, path in enumerate(paths):
        is_closed = (len(path) > 2 and pt_key(path[0]) == pt_key(path[-1]))
        if is_closed:
            path = path[:-1]
        draw_road_with_fillets(ax, path, width, color, fillet_radius, alpha, zorder, 
                               label if (i == 0 and label) else "", is_closed=is_closed, free_ends=free_ends)

def draw_network_squared(ax, segments, width, color, alpha=0.95, zorder=3.5, label=""):
    if not segments:
        return
        
    import collections
    import math
    
    adj = collections.defaultdict(list)
    
    def pt_key(p):
        return (round(p[0], 3), round(p[1], 3))
        
    for seg in segments:
        if not seg or len(seg) < 2:
            continue
        p1, p2 = seg[0], seg[1]
        k1, k2 = pt_key(p1), pt_key(p2)
        if k1 == k2:
            continue
        adj[k1].append(k2)
        adj[k2].append(k1)
        
    r = width / 2
    
    for i, seg in enumerate(segments):
        if not seg or len(seg) < 2:
            continue
        p1, p2 = list(seg[0]), list(seg[1])
        k1, k2 = pt_key(p1), pt_key(p2)
        
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        L = math.hypot(dx, dy)
        if L < 0.1:
            continue
            
        ux = dx / L
        uy = dy / L
        
        ext = min(r, L / 2)
        
        # Extend p1 if it is connected to other segments
        if len(adj[k1]) > 1:
            p1[0] -= ext * ux
            p1[1] -= ext * uy
            
        # Extend p2 if it is connected to other segments
        if len(adj[k2]) > 1:
            p2[0] += ext * ux
            p2[1] += ext * uy
            
        draw_orthogonal_line(ax, p1, p2, width, color, alpha, zorder, 
                             label if (i == 0 and label) else "", cap_p1=False, cap_p2=False)



plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

st.set_page_config(page_title="Roads Test", layout="wide")

# ── Shared sidebar: site + gate ────────────────────────────────────────────
st.sidebar.header("Site")
site_width  = st.sidebar.slider("Plot Width (A)",  100, 1000, 500, step=10)
site_length = st.sidebar.slider("Plot Length (B)", 100, 1000, 270, step=10)
wind_dir    = st.sidebar.selectbox("Wind Direction",
                                   ["North", "South", "East", "West"], index=2)

st.sidebar.divider()
st.sidebar.header("Site Gate")
gate_side  = st.sidebar.selectbox("Gate edge", ["N", "S", "E", "W"], index=0)
gate_ratio = st.sidebar.slider("Gate position along edge", 0.1, 0.9, 0.4, step=0.05)

st.sidebar.divider()
st.sidebar.header("Fixed Anchors")  # → §3.2
st.sidebar.subheader("Gate House")
gh_edge   = st.sidebar.selectbox("Edge (GH)",     ["N", "S", "E", "W"], index=0)
gh_ratio  = st.sidebar.slider("Position (GH)",    0.0, 1.0, 0.6, step=0.05)
gh_offset = st.sidebar.slider("Offset (GH)",      0, 50, 15, step=1)
bb_edge   = st.sidebar.selectbox("Boom Barrier Side (GH)", ["N", "S", "E", "W"], index=0)

st.sidebar.subheader("GIS")
gis_edge   = st.sidebar.selectbox("Edge (GIS)",   ["N", "S", "E", "W"], index=0)
gis_ratio  = st.sidebar.slider("Position (GIS)",  0.0, 1.0, 0.9, step=0.05)
gis_offset = st.sidebar.slider("Offset (GIS)",    0, 50, 15, step=1)

st.sidebar.subheader("RAW Water Tank")
water_edge   = st.sidebar.selectbox("Edge (RAW Water)", ["N", "S", "E", "W"], index=2)
water_ratio  = st.sidebar.slider("Position (RAW Water)", 0.0, 1.0, 0.2, step=0.05)
water_offset = st.sidebar.slider("Offset (RAW Water)",   0, 50, 0, step=1)

st.sidebar.divider()

if True:  # Phase 06 — Sketch roads
    st.title("Phase 06 — Block + Road Sketch")
    st.markdown("Reference: [Phase 06 Plan](file:///x:/CST%EB%B3%B8%EB%B6%80%20%28%EA%B5%AC%20%EA%B8%B0%EC%88%A0%EC%A7%80%EC%9B%90%EB%B6%80%20%ED%8F%B4%EB%8D%94%29/15.%20%EB%8B%A4%EB%A6%AC%EC%95%84/D-Brain/00_Input/Phase_06_Plan.md)")
    st.caption("Steps 1.1–1.5: blocks · ring road + spurs · rack network")

    st.sidebar.header("Phase 06 Settings")
    show_grid     = st.sidebar.checkbox("§2 — 2m Grid", value=False)
    show_alt_ring = st.sidebar.checkbox("Use 18 m inner corners (alternative ring road)", value=False)
    show_buffer       = st.sidebar.checkbox(f"§3.5.B — Block buffers ({ROAD_BUFFER}m / 16m)", value=False)
    show_rack_no_rack = st.sidebar.checkbox("§3.6.A — Rack baseline (no-rack: 8m / 16m)", value=False)
    show_rack_w_rack  = st.sidebar.checkbox("§3.6.A — Rack w-rack (8m / 16m / 24m / 30m)", value=False)
    show_a1_ring      = st.sidebar.checkbox("§3.4 — Ring Road + Spurs", value=True)
    show_rack_b1      = st.sidebar.checkbox("§3.6.B — Rack spines", value=True)
    show_spine_debug  = st.sidebar.checkbox("Show Spine Debug Visualizer", value=True)
    show_legend   = st.sidebar.checkbox("Legend", value=True)
    fix_seed      = st.sidebar.checkbox("Fix seed", value=True)
    seed_val      = st.sidebar.number_input("Seed", 0, 10000, 42, disabled=not fix_seed)

    if st.button("Generate Sketch", type="primary", use_container_width=True):
        if fix_seed:
            random.seed(int(seed_val))
        # Set ring road geometry based on UI toggle
        Core.Layout06.set_use_alt_ring_road(show_alt_ring)
        with st.spinner("Generating Phase 06 sketch..."):
            sketch = generate_sketch(  # → §3.1 Master Placement Sequence
                site_width, site_length, wind_dir,
                gate_side=gate_side, gate_ratio=gate_ratio,
                gh_edge=gh_edge,    gh_ratio=gh_ratio,    gh_offset=gh_offset,
                bb_edge=bb_edge,
                gis_edge=gis_edge,  gis_ratio=gis_ratio,  gis_offset=gis_offset,
                water_edge=water_edge, water_ratio=water_ratio, water_offset=water_offset,
            )
        if sketch is None:
            st.error("Could not place all blocks — try changing site size or parameters.")
            st.session_state["sketch06"] = None
        else:
            st.session_state["sketch06"] = sketch
            st.session_state["params06"] = (site_width, site_length)

    sketch = st.session_state.get("sketch06")
    if sketch is None:
        dbg = Core.Layout06._last_debug
        if dbg:
            st.error("Could not place all blocks — try changing site size or parameters.")
            st.markdown("#### Placement debug")
            attempts = dbg.get("total_attempts", 0)
            failed_at = dbg.get("failed_at", "?")
            section   = dbg.get("failed_section", "?")
            st.write(f"**Attempts:** {attempts} / {dbg.get('max_pool', '?')}  |  **Failed at:** `{failed_at}` ({section})")

            fail_counts = dbg.get("fail_counts", {})
            if fail_counts:
                st.markdown("**Block failure counts across all attempts:**")
                fc_rows = sorted([{"Block": k, "Fail count": v, "Fail %": f"{100*v//attempts}%"}
                                   for k, v in fail_counts.items()], key=lambda r: -r["Fail count"])
                st.dataframe(fc_rows, use_container_width=True, hide_index=True)

            last_placed = dbg.get("last_placed", {})
            ALL_BLOCKS = list(Core.Layout06.BLOCK_FOOTPRINTS.keys())
            st.markdown("**Last attempt — block placement status:**")
            status_rows = []
            for bname in ALL_BLOCKS:
                if bname in last_placed:
                    x, y, w, h = last_placed[bname]
                    status_rows.append({"Block": bname, "Status": "✓ placed",
                                        "x": round(x,1), "y": round(y,1), "w": round(w,1), "h": round(h,1)})
                elif bname == failed_at:
                    status_rows.append({"Block": bname, "Status": "✗ FAILED", "x": "-", "y": "-", "w": "-", "h": "-"})
                else:
                    status_rows.append({"Block": bname, "Status": "– not reached", "x": "-", "y": "-", "w": "-", "h": "-"})
            st.dataframe(status_rows, use_container_width=True, hide_index=True)
        else:
            st.info("Set parameters in the sidebar, then click **Generate Sketch**.")
        st.stop()

    sw, sl = st.session_state.get("params06", (site_width, site_length))
    blocks        = sketch["blocks"]
    ring_road     = sketch["ring_road"]
    gate_pt       = sketch["gate_point"]
    pb_center     = sketch["pb_center"]

    fig, ax = plt.subplots(figsize=(13, 8), dpi=110)

    # Site fill + boundary
    ax.fill([0,sw,sw,0,0], [0,0,sl,sl,0], color='#f0f8ff', zorder=0)
    ax.plot([0,sw,sw,0,0], [0,0,sl,sl,0], color='black', lw=1.2, zorder=1)

    # 2m grid
    if show_grid:
        cs = CELL_SIZE
        for i in range(int(sw // cs) + 1):
            ax.axvline(i * cs, color='#dddddd', lw=0.2, zorder=0.1)
        for j in range(int(sl // cs) + 1):
            ax.axhline(j * cs, color='#dddddd', lw=0.2, zorder=0.1)


    if show_a1_ring:  # → §3.4.A (ring road) · §3.4.B (gate spur) · §3.4.D (ring spur)
        # Ring road (loop)
        if ring_road:
            draw_road_with_fillets(ax, ring_road, width=8, color='#7f8c8d', fillet_radius=14.0, alpha=0.95, zorder=1.5,
                                   label='§3.4.A Ring Road', is_closed=True)

        # Gate & Ring spurs
        gs = sketch.get("gate_spur") or []
        rs = sketch.get("ring_spur") or []
        if gs and rs:
            combined_spur = list(rs) + list(gs)[1:]
            draw_road_with_fillets(ax, combined_spur, width=8, color='#7f8c8d', fillet_radius=14.0, alpha=0.95, zorder=1.5,
                                   label='§3.4.B/D Gate & Ring Spur', is_closed=False)
        else:
            if gs:
                draw_road_with_fillets(ax, gs, width=8, color='#7f8c8d', fillet_radius=14.0, alpha=0.95, zorder=1.5, is_closed=False)
            if rs:
                draw_road_with_fillets(ax, rs, width=8, color='#7f8c8d', fillet_radius=14.0, alpha=0.95, zorder=1.5, is_closed=False)


    # Default buffer halos per block — magnetic snap boundaries  [→ §3.5.B gap rules]
    #  - Rack blocks: 14m road buffer (so two rack blocks touching sit 28m apart)
    #  - No-rack blocks: 8m road buffer (so two no-rack touching sit 16m apart)
    if show_buffer:
        legended_buffers = set()
        for b in blocks:
            is_rack = b["name"] in Core.Layout06.RACK_BLOCKS
            snap_buf = Core.Layout06.ROAD_W_RACK_OFFSET if is_rack else Core.Layout06.ROAD_BUFFER
            color = '#2980b9' if is_rack else '#34495e'
            lbl = f'§3.5.B {snap_buf}m road snap buffer'
            
            xs = [b["x"] - snap_buf, b["x"] + b["width"] + snap_buf,
                  b["x"] + b["width"] + snap_buf, b["x"] - snap_buf, b["x"] - snap_buf]
            ys = [b["y"] - snap_buf, b["y"] - snap_buf,
                  b["y"] + b["height"] + snap_buf, b["y"] + b["height"] + snap_buf, b["y"] - snap_buf]
            
            ax.plot(xs, ys, color=color, linestyle='--', linewidth=1.0,
                    alpha=0.8, zorder=1.8,
                    label=lbl if lbl not in legended_buffers else "")
            legended_buffers.add(lbl)

    # Rack-block per-side buffer rectangles (Step A) for the 5 "need rack" blocks.  [→ §3.6.A]
    # 6 offsets total, split into two toggle groups:
    #   - "no rack" baseline (overlaps the default 8m+16m halos)
    #   - "with rack" (Case 1 / road 14m / Case 2 / b2b 28m)
    rack_buf = sketch.get("rack_buffers", {})
    if rack_buf:
        # (key, label, color, linestyle, linewidth, toggle_flag)
        rack_specs = [
            ("road_no_rack", '§3.6.A 8m road (no-rack)',   '#34495e', '--', 0.8, show_rack_no_rack),
            ("b2b_no_rack",  '§3.6.A 16m b2b (no-rack)',   '#c0392b', ':',  0.8, show_rack_no_rack),
            ("case1_rack",   '§3.6.A Case 1 CL (8m)',      '#00b894', '-',  1.6, show_rack_w_rack),
            ("road_w_rack",  '§3.6.A 16m road (w-rack)',   '#2980b9', '-',  1.2, show_rack_w_rack),
            ("case2_rack",   '§3.6.A Case 2 CL (24m)',     '#8e44ad', ':',  1.4, show_rack_w_rack),
            ("b2b_w_rack",   '§3.6.A 30m b2b (w-rack)',    '#e67e22', ':',  1.0, show_rack_w_rack),
        ]
        legended = {spec[0]: False for spec in rack_specs}
        for bname, offsets in rack_buf.items():
            for key, lbl, color, ls, lw, toggle in rack_specs:
                if not toggle or key not in offsets:
                    continue
                rx, ry, rw, rh = offsets[key]
                xs = [rx, rx + rw, rx + rw, rx, rx]
                ys = [ry, ry, ry + rh, ry + rh, ry]
                ax.plot(xs, ys, color=color, linestyle=ls, linewidth=lw,
                        alpha=0.9, zorder=2.5,
                        label=lbl if not legended[key] else "")
                legended[key] = True

    # Rack spines B-1..B-5  [→ §3.6.B]
    if show_rack_b1:
        rack_segments = sketch.get("rack_segments", [])
        with open("debug_draw.txt", "w", encoding="utf-8") as f:
            for seg in rack_segments:
                f.write(f"plotting: {seg}\n")
        draw_network_squared(ax, rack_segments, width=6, color='#d35400', zorder=3.5,
                             label='§3.6.B Rack Spines')

    if show_spine_debug:
        spine_centerlines = sketch.get("spine_centerlines") or []
        water_cluster_segments = sketch.get("water_cluster_segments") or []
        
        # Plot raw spine centerlines as thick dashed green lines
        for i, seg in enumerate(spine_centerlines):
            p1, p2 = seg
            ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color='#2ecc71', linestyle='--', linewidth=2.5, alpha=0.9, zorder=3.8,
                    label='Raw Spine Centerlines (PB-CT)' if i == 0 else "")
            ax.plot([p1[0], p2[0]], [p1[1], p2[1]], 'o', color='#27ae60', markersize=6, zorder=3.9)
            
        # Plot water cluster segments as thick dashed cyan lines
        for i, seg in enumerate(water_cluster_segments):
            p1, p2 = seg
            ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color='#00d2d3', linestyle='--', linewidth=2.5, alpha=0.9, zorder=3.8,
                    label='Water Cluster Spine (Raw)' if i == 0 else "")
            ax.plot([p1[0], p2[0]], [p1[1], p2[1]], 'o', color='#01a3a4', markersize=6, zorder=3.9)
                
        # Candidate points (B-2, B-3)  [→ §3.6.B]
        # (Disabled by user request)
        # rack_candidates = sketch.get("rack_candidates", [])
        # for i, pt in enumerate(rack_candidates):
        #     ax.plot(pt[0], pt[1], 'o', color='#bdc3c7', markersize=4, zorder=3.6, 
        #             label='§3.6.B B-2/B-3 Candidates' if i==0 else "")

        # Water Triangle (B-4)  [→ §3.6.B]
        # (Disabled by user request)
        # water_triangle = sketch.get("water_triangle", [])
        # for i, pt in enumerate(water_triangle):
        #     ax.plot(pt[0], pt[1], '*', color='#f1c40f', markersize=12, markeredgecolor='black', zorder=3.7, 
        #             label='§3.6.B B-4 Triangle' if i==0 else "")
        # if len(water_triangle) == 3:
        #     # Draw lines connecting them
        #     wx, wy = zip(*(water_triangle + [water_triangle[0]]))
        #     ax.plot(wx, wy, color='#f1c40f', linestyle=':', linewidth=1, zorder=3.6)

    # Boom Barrier  [→ §3.1 step 5]
    boom_barrier = sketch.get("boom_barrier", [])
    if boom_barrier and len(boom_barrier) == 2:
        xs, ys = zip(*boom_barrier)
        ax.plot(xs, ys, color='#e74c3c', linewidth=4, linestyle='-', zorder=4.0, label='§3.1·5 Boom Barrier')

    # Gate Death Zone  [→ §3.4.C]
    gate_death_zone = sketch.get("gate_death_zone")
    if gate_death_zone:
        gx, gy, gw, gh = gate_death_zone
        import matplotlib.patches as patches
        rect = patches.Rectangle((gx, gy), gw, gh, linewidth=1.5, edgecolor='#c0392b',
                                 facecolor='#e74c3c', alpha=0.2, hatch='///', zorder=1.1, label='§3.4.C Gate Death Zone')
        ax.add_patch(rect)


    # Blocks (circles for Tanks + Flare per Groups.SHAPES, rectangles otherwise)
    for b in blocks:
        x, y, w, h = b["x"], b["y"], b["width"], b["height"]
        if SHAPES.get(b["name"]) == "circle":
            r = min(w, h) / 2
            cx, cy = x + w / 2, y + h / 2
            ax.add_patch(mpatches.Circle((cx, cy), r, facecolor=b["color"], alpha=0.55, zorder=2))
            ax.add_patch(mpatches.Circle((cx, cy), r, fill=False, edgecolor=b["color"], lw=1.0, zorder=2.1))
        else:
            ax.fill([x,x+w,x+w,x,x], [y,y,y+h,y+h,y], color=b["color"], alpha=0.55, zorder=2)
            ax.plot([x,x+w,x+w,x,x], [y,y,y+h,y+h,y], color=b["color"], lw=1.0, zorder=2.1)
        ax.text(x + w/2, y + h/2, b["name"], color='white', fontsize=5.5,
                fontweight='bold', ha='center', va='center', zorder=3,
                bbox=dict(facecolor='#333', alpha=0.75, edgecolor='none', pad=1))

    # Gate marker
    gx, gy = gate_pt
    ax.plot(gx, gy, '^', color='#27ae60', markersize=14, zorder=6,
            markeredgecolor='white', markeredgewidth=1.0)
    ax.text(gx, gy + 8, 'GATE', color='#27ae60', fontsize=9,
            fontweight='bold', ha='center', va='bottom', zorder=6)

    ax.set_xlim(-20, sw + 20)
    ax.set_ylim(-20, sl + 20)
    ax.set_aspect('equal', adjustable='box')
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values(): sp.set_visible(False)
    if show_legend:
        ax.legend(loc='upper left', fontsize=8, framealpha=0.9)

    plt.tight_layout(pad=0.4)
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)

    # Placement pass banner — shown below the layout
    _dbg = Core.Layout06._last_debug
    _tol_label = _dbg.get("boundary_pass_label", "")
    if _tol_label:
        if "pass 1" in _tol_label:
            st.success(f"✓ {_tol_label} — all blocks fit with 18m inner margin")
        elif "pass 2" in _tol_label:
            st.info(f"ℹ {_tol_label} — blocks fit inside plot boundary (no margin)")
        else:
            st.warning(f"⚠ {_tol_label} — tight site; some blocks may slightly exceed boundary")

    # §3.7.E debug expander
    with st.expander("§3.3 Debug — PB gate-side stop line"):
        gc = Core.Layout06._last_debug.get("pb_gate_check")
        if gc:
            st.json(gc)
            ne = gc.get("gh_near_edge (closest to center)")
            if ne == "buf_bottom":
                ok = gc["ring_top"] <= gc["buf_bottom"] + 0.01
                st.write(f"ring_top {gc['ring_top']} ≤ buf_bottom {gc['buf_bottom']} ? → {'✅' if ok else '❌ ABOVE'}")
            elif ne == "buf_top":
                ok = gc["ring_bottom"] >= gc["buf_top"] - 0.01
                st.write(f"ring_bottom {gc['ring_bottom']} ≥ buf_top {gc['buf_top']} ? → {'✅' if ok else '❌'}")
            elif ne == "buf_left":
                ok = gc["ring_right"] <= gc["buf_left"] + 0.01
                st.write(f"ring_right {gc['ring_right']} ≤ buf_left {gc['buf_left']} ? → {'✅' if ok else '❌'}")
            elif ne == "buf_right":
                ok = gc["ring_left"] >= gc["buf_right"] - 0.01
                st.write(f"ring_left {gc['ring_left']} ≥ buf_right {gc['buf_right']} ? → {'✅' if ok else '❌'}")
        else:
            st.warning("no pb_gate_check in debug")

    with st.expander("§3.6.B Debug — PB-CT Spine Creation"):
        sc = Core.Layout06._last_debug.get("spine_creation")
        if sc:
            st.write(f"**Power Block Case:** `{sc.get('pb_case')}`")
            st.write(f"**Cooling Tower Case:** `{sc.get('ct_case')}`")
            st.write(f"**Horizontal Overlap?** `{sc.get('is_horizontal')}` | **Vertical Overlap?** `{sc.get('is_vertical')}`")
            st.write(f"**Overlap Detected?** `{sc.get('overlap')}`")
        else:
            st.warning("no spine_creation in debug metadata")

        # Table of all rack spans
        import pandas as pd
        import math

        segments_data = []

        # 1. Spine centerlines
        spine_centerlines = sketch.get("spine_centerlines") or []
        for i, s in enumerate(spine_centerlines):
            x1, y1 = s[0]
            x2, y2 = s[1]
            L = math.hypot(x2 - x1, y2 - y1)
            direction = "Horizontal" if abs(y2 - y1) < 0.1 else ("Vertical" if abs(x2 - x1) < 0.1 else "Skewed")
            segments_data.append({
                "Span Type": f"Spine Centerline [{i+1}]",
                "Start Point": f"({round(x1, 1)}, {round(y1, 1)})",
                "End Point": f"({round(x2, 1)}, {round(y2, 1)})",
                "Length (m)": round(L, 2),
                "Direction": direction
            })

        # 2. Water cluster segments
        water_cluster_segments = sketch.get("water_cluster_segments") or []
        for i, s in enumerate(water_cluster_segments):
            x1, y1 = s[0]
            x2, y2 = s[1]
            L = math.hypot(x2 - x1, y2 - y1)
            direction = "Horizontal" if abs(y2 - y1) < 0.1 else ("Vertical" if abs(x2 - x1) < 0.1 else "Skewed")
            segments_data.append({
                "Span Type": f"Water Cluster Spine [{i+1}]",
                "Start Point": f"({round(x1, 1)}, {round(y1, 1)})",
                "End Point": f"({round(x2, 1)}, {round(y2, 1)})",
                "Length (m)": round(L, 2),
                "Direction": direction
            })

        # 3. Final rack segments (spines + connections)
        rack_segments = sketch.get("rack_segments") or []
        for i, s in enumerate(rack_segments):
            x1, y1 = s[0]
            x2, y2 = s[1]
            L = math.hypot(x2 - x1, y2 - y1)
            direction = "Horizontal" if abs(y2 - y1) < 0.1 else ("Vertical" if abs(x2 - x1) < 0.1 else "Skewed")
            segments_data.append({
                "Span Type": f"Final Connected Span [{i+1}]",
                "Start Point": f"({round(x1, 1)}, {round(y1, 1)})",
                "End Point": f"({round(x2, 1)}, {round(y2, 1)})",
                "Length (m)": round(L, 2),
                "Direction": direction
            })

        if segments_data:
            st.markdown("#### All Rack Spans / Segments")
            df_segs = pd.DataFrame(segments_data)
            st.dataframe(df_segs, use_container_width=True, hide_index=True)
            
            # Add a copy-pasteable data block
            st.markdown("#### 📋 Copy-Paste Coordinates")
            st.code(
                f"spine_centerlines = {spine_centerlines}\n\n"
                f"water_cluster_segments = {water_cluster_segments}\n\n"
                f"final_rack_segments = {rack_segments}",
                language="python"
            )


    # Stats
    st.divider()
    st.markdown("#### Block stats")
    rows = [{"Block": b["name"], "X (m)": b["x"], "Y (m)": b["y"],
             "W (m)": b["width"], "H (m)": b["height"]} for b in blocks]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    c1, c2 = st.columns(2)
    c1.metric("Blocks placed", len(blocks))
    c2.metric("Grid cell size", f"{CELL_SIZE}m")

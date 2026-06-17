"""
Core/Exporter.py
Exports a generated layout to a DXF file using ezdxf.
No Streamlit imports — pure geometry output.
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
    ("CABLE_TUNNEL",        5,               "CONTINUOUS"),   # purple (ACI 5)
    ("LPG_METERING",        colors.RED,      "CONTINUOUS"),
    ("FLARE",               30,              "CONTINUOUS"),   # orange (ACI 30)
    ("WT_WWT",              4,               "CONTINUOUS"),   # light blue (ACI 4)
    ("WATER",               3,               "CONTINUOUS"),   # teal (ACI 3)
    ("PIPE_RACK",           colors.GRAY,     "DASHED"),
    ("MAIN_RACK",           colors.GRAY,     "DASHED"),
    ("UTILITY_RACK",        colors.GRAY,     "DASHED"),
    ("LABELS",              colors.WHITE,    "CONTINUOUS"),
    ("DIMENSIONS",          colors.GRAY,     "CONTINUOUS"),
]

# Map group names to layer names
GROUP_LAYER_MAP = {
    "Power Block":    "POWER_BLOCK",
    "Cooling Tower":  "COOLING_TOWER",
    "Admin Building": "ADMIN_BUILDING",
    "Gate House":     "GATE_HOUSE",
    "Cable Tunnel":   "CABLE_TUNNEL",
    "LPG/Metering":   "LPG_METERING",
    "Flare":          "FLARE",
    "WT/WWT":         "WT_WWT",
    "Water":          "WATER",
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


def export_to_dxf(layout, site_width, site_length):
    """
    Convert a layout dict (from Core/Main.py) to a DXF binary stream.

    Args:
        layout      : dict with keys 'groups', 'racks', 'scoring'
        site_width  : float — site width in metres
        site_length : float — site length in metres

    Returns:
        DXF content as a string, ready for st.download_button.
    """
    doc = ezdxf.new(dxfversion="R2010")
    doc.header["$INSUNITS"] = 6   # 6 = metres

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
    _add_rect(msp, 0, 0, site_width, site_length, "SITE_BOUNDARY")
    _add_label(msp, f"Site  {site_width:.0f} x {site_length:.0f} m",
               site_width / 2, site_length + 6, 3.0, "LABELS")

    # ── 2. Road Setback (5 m) ───────────────────────────────────────────────
    s = 5
    if site_width > 2*s and site_length > 2*s:
        _add_rect(msp, s, s, site_width - 2*s, site_length - 2*s, "ROAD_SETBACK")
        msp.add_text(
            "Primary Road Setback (5 m)",
            dxfattribs={"layer": "LABELS", "height": 2.0,
                        "insert": (s + 1, s + 1)},
        )

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

    # ── 4. Polyline Racks ───────────────────────────────────────────────────
    for rack in layout.get("racks", []):
        layer = RACK_LAYER_MAP.get(rack["name"], "PIPE_RACK")
        for p1, p2 in rack.get("segments", []):
            x1, y1 = p1
            x2, y2 = p2
            msp.add_line((x1, y1), (x2, y2), dxfattribs={"layer": layer})

    # ── 5. Score annotation ─────────────────────────────────────────────────
    total   = layout["scoring"]["total_penalty"]
    passing = sum(1 for r in layout["scoring"]["results"] if r["passed"])
    n_rules = len(layout["scoring"]["results"])
    score_text = f"Penalty Score: {total:,.0f} pts  |  {passing}/{n_rules} rules passing"
    msp.add_text(
        score_text,
        dxfattribs={"layer": "LABELS", "height": 3.0,
                    "insert": (0, -15)},
    )

    # ── Serialise to String ─────────────────────────────────────────────────
    stream = io.StringIO()
    doc.write(stream)
    return stream.getvalue()

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
    # (name,            color_index,  linetype)
    ("SITE_BOUNDARY",   colors.WHITE,   "CONTINUOUS"),
    ("ROAD_SETBACK",    colors.RED,     "DASHED"),
    ("GATE_HOUSE",      colors.YELLOW,  "CONTINUOUS"),
    ("POWER_BLOCK",     colors.CYAN,    "CONTINUOUS"),
    ("COOLING_TOWER",   colors.GREEN,   "CONTINUOUS"),
    ("ADMIN_BUILDING",  colors.MAGENTA, "CONTINUOUS"),
    ("LABELS",          colors.WHITE,   "CONTINUOUS"),
    ("DIMENSIONS",      colors.GRAY,    "CONTINUOUS"),
]


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
        layout      : dict with keys 'groups', 'scoring', 'pb_x' etc.
        site_width  : float — site width in metres
        site_length : float — site length in metres

    Returns:
        io.BytesIO stream containing the DXF file, ready for st.download_button.
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
    _add_label(msp, f"Site  {site_width:.0f} × {site_length:.0f} m",
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

    # ── 3. Gate House ───────────────────────────────────────────────────────
    GH_W, GH_H = 12, 8
    gh_x = site_width / 2 - GH_W / 2
    gh_y = -GH_H
    _add_rect(msp, gh_x, gh_y, GH_W, GH_H, "GATE_HOUSE")
    _add_label(msp, "Gate House", site_width / 2, gh_y - 3, 2.0, "LABELS")

    # ── 4. Building Groups ──────────────────────────────────────────────────
    layer_map = {
        "Power Block":    "POWER_BLOCK",
        "Cooling Tower":  "COOLING_TOWER",
        "Admin Building": "ADMIN_BUILDING",
    }

    for group in layout["groups"]:
        x, y = group["x"], group["y"]
        w, h = group["width"], group["height"]
        layer = layer_map.get(group["name"], "SITE_BOUNDARY")

        # Outline
        _add_rect(msp, x, y, w, h, layer)

        # Centre cross-hair (2 short lines)
        cx, cy = x + w/2, y + h/2
        tick = min(w, h) * 0.08
        msp.add_line((cx - tick, cy), (cx + tick, cy), dxfattribs={"layer": layer})
        msp.add_line((cx, cy - tick), (cx, cy + tick), dxfattribs={"layer": layer})

        # Name label inside block
        _add_label(msp, group["name"], cx, cy, min(w, h) * 0.10, "LABELS")

        # Dimension: width and height annotations
        # Width arrow below
        msp.add_linear_dim(
            base=(x, y - 6),
            p1=(x, y),
            p2=(x + w, y),
            dimstyle="EZ_M_100_H25_CM",
            override={"dimtxt": 2.0},
            dxfattribs={"layer": "DIMENSIONS"},
        ).render()
        # Height arrow to the right
        msp.add_linear_dim(
            base=(x + w + 6, y),
            p1=(x + w, y),
            p2=(x + w, y + h),
            angle=90,
            dimstyle="EZ_M_100_H25_CM",
            override={"dimtxt": 2.0},
            dxfattribs={"layer": "DIMENSIONS"},
        ).render()

    # ── 5. Score annotation ─────────────────────────────────────────────────
    total   = layout["scoring"]["total_penalty"]
    passing = sum(1 for r in layout["scoring"]["results"] if r["passed"])
    score_text = f"Penalty Score: {total:,.0f} pts  |  {passing}/6 rules passing"
    msp.add_text(
        score_text,
        dxfattribs={"layer": "LABELS", "height": 3.0,
                    "insert": (0, -GH_H - 8)},
    )

    # ── Serialise to BytesIO ────────────────────────────────────────────────
    stream = io.BytesIO()
    doc.write(stream)
    stream.seek(0)
    return stream

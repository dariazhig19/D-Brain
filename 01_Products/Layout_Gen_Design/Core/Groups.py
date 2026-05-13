import matplotlib.pyplot as plt

# ── Color Palette ──────────────────────────────────────────────────────────

GROUP_COLORS = {
    "Power Block":    "#4a90d9",   # blue
    "Cooling Tower":  "#7ed6a0",   # green
    "Admin Building": "#f5a623",   # orange
    "Gate House":     "#5c4a32",   # brown
    "Cable Tunnel":   "#8e44ad",   # purple
    "LPG/Metering":   "#e74c3c",   # red
    "Flare":          "#e67e22",   # dark orange
    "WT/WWT":         "#3498db",   # light blue
    "Water":          "#1abc9c",   # teal
    "GIS":            "#2c3e50",   # dark navy
    "Warehouse":      "#d35400",   # burnt orange
}

RACK_COLORS = {
    "Pipe Rack":    "#95a5a6",   # gray
    "Main Rack":    "#7f8c8d",   # dark gray
    "Utility Rack": "#bdc3c7",   # silver
}


# ── Phase 03 backward-compat ──────────────────────────────────────────────

def get_groups(site_width, site_length, pb_x=None, pb_y=None, ct_x=None, ct_y=None, adm_x=None, adm_y=None):
    """
    Define the 3 main building groups with their dimensions and default positions.
    Positions are calculated based on site dimensions, or use explicitly provided absolute coordinates.
    """
    # Footprint dimensions (confirmed in meters, Phase 05)
    pw_w, pw_h = 150, 150  # Power Block footprint
    ct_w, ct_h = 40,  183  # Cooling Tower footprint
    adm_w, adm_h = 30, 25  # Admin Building footprint

    return [
        {   # Power Block — centered on site
            "name": "Power Block",
            "x": pb_x if pb_x is not None else (site_width - pw_w) / 2,
            "y": pb_y if pb_y is not None else (site_length - pw_h) / 2,
            "width": pw_w, 
            "height": pw_h,
            "color": "#4a90d9",
        },
        {   # Cooling Tower — right edge, vertically centered
            "name": "Cooling Tower",
            "x": ct_x if ct_x is not None else site_width - ct_w - 10,
            "y": ct_y if ct_y is not None else (site_length - ct_h) / 2,
            "width": ct_w, 
            "height": ct_h,
            "color": "#7ed6a0",
        },
        {   # Admin Building — lower-left
            "name": "Admin Building",
            "x": adm_x if adm_x is not None else 20,
            "y": adm_y if adm_y is not None else 20,
            "width": adm_w, 
            "height": adm_h,
            "color": "#f5a623",
        },
    ]


# ── Phase 04: Full group catalog ──────────────────────────────────────────

# Footprint dimensions (width × height in metres) — Phase 05 confirmed
FOOTPRINTS = {
    "Power Block":    (150, 150),
    "Cooling Tower":  (40,  183),
    "Admin Building": (30,  25),
    "Gate House":     (12,  12),
    "GIS":            (110, 51),
    "Warehouse":      (59,  40),
    "LPG/Metering":   (40,  30),
    "Flare":          (40,  40),
    "WT/WWT":         (81,  56),
    "Water":          (40,  40),
}

# Rack metadata (width in metres = physical corridor width)
RACK_WIDTHS = {
    "Pipe Rack":    6,
    "Main Rack":    8,
    "Utility Rack": 6,
    "Cable Tunnel": 3,
}

# ── Color Palette (Phase 04/05) ───────────────────────────────────────────

GROUP_COLORS = {
    "Power Block":    "#4a90d9",
    "Cooling Tower":  "#7ed6a0",
    "Admin Building": "#f5a623",
    "Gate House":     "#9b59b6",
    "GIS":            "#2c3e50",
    "Warehouse":      "#d35400",
    "LPG/Metering":   "#f1c40f",
    "Flare":          "#e74c3c",
    "WT/WWT":         "#34495e",
    "Water":          "#00bcd4",
}

RACK_COLORS = {
    "Pipe Rack":    "#f1c40f", # Yellow
    "Main Rack":    "#2ecc71", # Green
    "Utility Rack": "#9b59b6", # Purple
    "Cable Tunnel": "#555555", # Dark Grey
}


def get_all_groups(site_width, site_length, positions=None):
    """
    Return all 11 rectangle groups for Phase 05.

    Args:
        site_width  : float — plot width in metres
        site_length : float — plot length in metres
        positions   : dict  — optional {group_name: (x, y)} overrides.
                      If None or missing for a group, uses default position.

    Returns:
        list of group dicts with keys: name, x, y, width, height, color
    """
    if positions is None:
        positions = {}

    # Default positions for 500 x 270 site (Phase 05)
    defaults = {
        "Power Block":    ((site_width - 150) / 2, (site_length - 150) / 2),
        "Cooling Tower":  (site_width - 40 - 15,   (site_length - 183) / 2),
        "Admin Building": (site_width / 2 - 15,     site_length - 25 - 30),
        "Gate House":     (site_width / 2 - 6,      site_length - 12),
        "GIS":            (site_width - 110 - 15,   site_length - 51 - 15),
        "Warehouse":      (15,                      15),
        "LPG/Metering":   (15,                      site_length - 30 - 15),
        "Flare":          (site_width - 40 - 15,    15),
        "WT/WWT":         (15,                      site_length / 2 - 28),
        "Water":          (15,                      site_length / 2 + 35),
    }

    groups = []
    for name, (w, h) in FOOTPRINTS.items():
        x, y = positions.get(name, defaults[name])
        groups.append({
            "name":   name,
            "x":      x,
            "y":      y,
            "width":  w,
            "height": h,
            "color":  GROUP_COLORS[name],
        })
    return groups


def get_all_racks(groups, rack_segments=None):
    """
    Return all 3 polyline racks for Phase 04.

    Each rack consists of one or more straight line segments connecting buildings.

    Args:
        groups        : list of group dicts
        rack_segments : dict — optional {rack_name: [((x1,y1), (x2,y2)), ...]} overrides

    Returns:
        list of rack dicts with keys: name, type, segments, color, width_m
    """
    if rack_segments is None:
        rack_segments = {}

    racks = []
    for name, width_m in RACK_WIDTHS.items():
        segments = rack_segments.get(name, [])
        racks.append({
            "name":     name,
            "type":     "rack",
            "segments": segments,
            "color":    RACK_COLORS[name],
            "width_m":  width_m,
        })
    return racks


# ── Drawing helpers ────────────────────────────────────────────────────────

def draw_group(ax, group):
    """
    Render a group block as a colored rectangle using coordinate lines (ax.plot).
    """
    x, y, w, h = group["x"], group["y"], group["width"], group["height"]
    
    # 5-point closed contour
    gx = [x,   x+w, x+w, x,   x]
    gy = [y,   y,   y+h, y+h, y]
    
    # Fill with transparency
    ax.fill(gx, gy, color=group["color"], alpha=0.5, zorder=1)
    
    # Border line
    ax.plot(gx, gy, color="black", linewidth=0.8, zorder=2)
    
    # Wrap text if there are spaces or slashes
    name_str = group["name"].replace(" ", "\n").replace("/", "/\n")
    
    # Group label in the center
    ax.text(x + w/2, y + h/2, name_str,
            ha='center', va='center', fontsize=7, fontweight='bold', zorder=3)


def draw_rack(ax, rack):
    """
    Render a rack as dashed polylines for all its segments.
    """
    if not rack["segments"]:
        return

    # Draw all segments
    for idx, (p1, p2) in enumerate(rack["segments"]):
        x1, y1 = p1
        x2, y2 = p2
        ax.plot([x1, x2], [y1, y2],
                color=rack["color"], linewidth=2.5, linestyle='--',
                solid_capstyle='round', zorder=1, alpha=0.8)

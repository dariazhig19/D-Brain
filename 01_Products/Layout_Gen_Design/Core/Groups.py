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
    # Footprint dimensions (estimated in meters)
    pw_w, pw_h = 120, 80   # Power Block footprint
    ct_w, ct_h = 60,  80   # Cooling Tower footprint
    adm_w, adm_h = 50, 40  # Admin Building footprint

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

# Footprint dimensions (width × height in metres)
FOOTPRINTS = {
    "Power Block":    (120, 80),
    "Cooling Tower":  (60,  80),
    "Admin Building": (50,  40),
    "Gate House":     (12,   8),
    "Cable Tunnel":   (60,   3),
    "LPG/Metering":   (40,  30),
    "Flare":          (20,  20),
    "WT/WWT":         (50,  40),
    "Water":          (40,  40),
}

# Rack metadata (width in metres = physical corridor width)
RACK_WIDTHS = {
    "Pipe Rack":    6,
    "Main Rack":    8,
    "Utility Rack": 6,
}


def get_all_groups(site_width, site_length, positions=None):
    """
    Return all 9 rectangle groups for Phase 04.

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

    # Default positions (reasonable starting placement)
    defaults = {
        "Power Block":    ((site_width - 120) / 2, (site_length - 80) / 2),
        "Cooling Tower":  (site_width - 60 - 10,   (site_length - 80) / 2),
        "Admin Building": (20,                      20),
        "Gate House":     (site_width / 2 - 6,       0),
        "Cable Tunnel":   ((site_width - 60) / 2,   (site_length - 80) / 2 - 10),
        "LPG/Metering":   (20,                      site_length - 30 - 20),
        "Flare":          (site_width - 20 - 20,    site_length - 20 - 20),
        "WT/WWT":         (20,                      site_length / 2 - 20),
        "Water":          (20,                      site_length / 2 + 30),
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


def get_all_racks(groups, rack_endpoints=None):
    """
    Return all 3 polyline racks for Phase 04.

    Each rack is a straight line between two points.
    Default endpoints connect related groups.

    Args:
        groups         : list of group dicts (to derive default endpoints)
        rack_endpoints : dict — optional {rack_name: ((x1,y1), (x2,y2))} overrides

    Returns:
        list of rack dicts with keys: name, type, start, end, color, width_m
    """
    if rack_endpoints is None:
        rack_endpoints = {}

    by_name = {g["name"]: g for g in groups}

    def _center(g):
        return g["x"] + g["width"] / 2, g["y"] + g["height"] / 2

    def _edge_mid_right(g):
        return g["x"] + g["width"], g["y"] + g["height"] / 2

    def _edge_mid_left(g):
        return g["x"], g["y"] + g["height"] / 2

    def _edge_mid_top(g):
        return g["x"] + g["width"] / 2, g["y"] + g["height"]

    # Default rack routes (straight lines between groups)
    pb = by_name.get("Power Block")
    ct = by_name.get("Cooling Tower")
    ww = by_name.get("WT/WWT")

    default_routes = {
        "Pipe Rack":    (_edge_mid_right(pb), _edge_mid_left(ct))  if pb and ct else ((0,0),(100,0)),
        "Main Rack":    (_edge_mid_top(pb),   (pb["x"] + pb["width"]/2, pb["y"] + pb["height"] + 40)) if pb else ((0,0),(0,100)),
        "Utility Rack": (_edge_mid_right(ww), (ww["x"] + ww["width"] + 60, ww["y"] + ww["height"]/2)) if ww else ((0,0),(100,0)),
    }

    racks = []
    for name, width_m in RACK_WIDTHS.items():
        start, end = rack_endpoints.get(name, default_routes[name])
        racks.append({
            "name":    name,
            "type":    "rack",
            "start":   start,
            "end":     end,
            "color":   RACK_COLORS[name],
            "width_m": width_m,
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
    
    # Group label in the center
    ax.text(x + w/2, y + h/2, group["name"],
            ha='center', va='center', fontsize=7, fontweight='bold', zorder=3)


def draw_rack(ax, rack):
    """
    Render a rack as a dashed polyline (straight line between start and end).
    """
    x1, y1 = rack["start"]
    x2, y2 = rack["end"]

    # Draw the rack line (thick dashed)
    ax.plot([x1, x2], [y1, y2],
            color=rack["color"], linewidth=2.5, linestyle='--',
            solid_capstyle='round', zorder=1, alpha=0.8)

    # Label at midpoint
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    ax.text(mx, my, rack["name"],
            ha='center', va='bottom', fontsize=5.5, fontweight='bold',
            color=rack["color"], zorder=3,
            bbox=dict(boxstyle='round,pad=0.15', fc='white', ec=rack["color"],
                      alpha=0.85, lw=0.5))

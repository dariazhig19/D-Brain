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
    "Admin Building": (50,  40),   # 30x25 building + 50 cars parking (~1250 sqm)
    "Gate House":     (20,  20),   # 12x12 building + 10 cars parking (~250 sqm)
    "GIS":            (110, 51),
    "Warehouse":      (90,  55),   # 59x40 building + 100 cars parking (~2500 sqm)
    "Flare":          (40,  40),   # Ø40 Flare Stack
    "WT/WWT":         (100, 80),   # 81x56 WT/WWT building + space for Clarifiers, Tanks
    "RAW Water Tank": (37,  37),   # Ø37 Raw Tank
    "Demi Water Tank":(25,  12),   # (x2) Ø10 Demi Tanks side-by-side
}

# Rendering Shapes
SHAPES = {
    "Flare": "circle",
    "RAW Water Tank": "circle"
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
    "Warehouse":      "#e67e22",
    "Flare":          "#e74c3c",
    "WT/WWT":         "#34495e",
    "RAW Water Tank": "#00bcd4",
    "Demi Water Tank":"#00bcd4",
}

RACK_COLORS = {
    "Pipe Rack":    "#f1c40f", # Yellow
    "Main Rack":    "#2ecc71", # Green
    "Utility Rack": "#9b59b6", # Purple
    "Cable Tunnel": "#555555", # Dark Grey
}


# ── Entrance point computation ─────────────────────────────────────────────

def compute_entrance_points(group, pb_center=None):
    """Compute entrance point(s) for a building.

    Rules:
    - Power Block: 4 entrances, one at the center of each side.
    - All other buildings: 1 entrance on the side facing the Power Block.
      Determines which side of the building is closest to PB center and
      places the entrance at the center of that side.
      If pb_center is None, falls back to center of longest side.

    Since rotated buildings already have swapped width/height in the
    group dict, the logic works automatically for rotated buildings.

    Returns:
        list of (x, y) world coordinates for each entrance point.
    """
    x, y, w, h = group["x"], group["y"], group["width"], group["height"]
    name = group["name"]

    if name == "Power Block":
        # 4 entrances: center of each side
        return [
            (x + w / 2, y),          # South (bottom)
            (x + w / 2, y + h),      # North (top)
            (x,         y + h / 2),  # West  (left)
            (x + w,     y + h / 2),  # East  (right)
        ]

    # For all other buildings: entrance on the side facing PB
    sides = {
        "S": (x + w / 2, y),          # bottom edge center
        "N": (x + w / 2, y + h),      # top edge center
        "W": (x,         y + h / 2),  # left edge center
        "E": (x + w,     y + h / 2),  # right edge center
    }

    if pb_center is not None:
        # Pick the side whose center point is closest to PB center
        best_side = min(sides, key=lambda s: (
            (sides[s][0] - pb_center[0]) ** 2 + (sides[s][1] - pb_center[1]) ** 2
        ))
        return [sides[best_side]]

    # Fallback: center of longest side
    if w >= h:
        return [sides["S"]]
    else:
        return [sides["W"]]


def compute_gate_point(side, ratio, site_w, site_l):
    """Compute the site gate world coordinate on the plot boundary.

    Args:
        side:   "N" | "S" | "E" | "W" — which boundary edge.
        ratio:  0.0–1.0 along that edge (0.5 = center).
        site_w: plot width in metres.
        site_l: plot length in metres.

    Returns:
        (x, y) world coordinate on the boundary.
    """
    if side == "S":
        return (site_w * ratio, 0)
    elif side == "N":
        return (site_w * ratio, site_l)
    elif side == "W":
        return (0, site_l * ratio)
    elif side == "E":
        return (site_w, site_l * ratio)
    else:
        raise ValueError(f"gate side must be N/S/E/W, got {side!r}")


def get_all_groups(site_width, site_length, positions=None):
    """
    Return all 11 rectangle groups for Phase 05.

    Args:
        site_width  : float — plot width in metres
        site_length : float — plot length in metres
        positions   : dict  — optional {group_name: (x, y) or (x, y, rotated)} overrides.
                      `rotated=True` swaps (width, height) → 90° rotation.
                      If None or missing for a group, uses default position (unrotated).

    Returns:
        list of group dicts with keys: name, x, y, width, height, color, rotated
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
        "Flare":          (site_width - 40 - 15,    15),
        "WT/WWT":         (15,                      site_length / 2 - 28),
        "RAW Water Tank": (15,                      site_length / 2 + 35),
        "Demi Water Tank":(15 + 40,                 site_length / 2 + 35),
    }

    groups = []
    for name, (fw, fh) in FOOTPRINTS.items():
        pos = positions.get(name, defaults[name])
        x, y = pos[0], pos[1]
        rotated = pos[2] if len(pos) >= 3 else False
        w, h = (fh, fw) if rotated else (fw, fh)
        group = {
            "name":    name,
            "x":       x,
            "y":       y,
            "width":   w,
            "height":  h,
            "color":   GROUP_COLORS[name],
            "rotated": rotated,
        }
        groups.append(group)

    # Find Power Block center for entrance direction
    pb = next((g for g in groups if g["name"] == "Power Block"), None)
    pb_center = None
    if pb:
        pb_center = (pb["x"] + pb["width"] / 2, pb["y"] + pb["height"] / 2)

    # Compute entrance points for all groups (facing PB)
    for group in groups:
        group["entrance_points"] = compute_entrance_points(group, pb_center=pb_center)

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
    Render a group block as a colored shape. Supports rectangles and circles.
    """
    x, y, w, h = group["x"], group["y"], group["width"], group["height"]
    name = group["name"]
    color = group["color"]
    
    shape = SHAPES.get(name, "rectangle")
    
    if shape == "circle":
        # Draw as a circle using width as diameter
        radius = w / 2
        cx, cy = x + radius, y + radius
        import matplotlib.patches as patches
        
        # Fill
        circle_fill = patches.Circle((cx, cy), radius, facecolor=color, alpha=0.5, zorder=1)
        ax.add_patch(circle_fill)
        # Outline
        circle_line = patches.Circle((cx, cy), radius, fill=False, edgecolor=color, lw=1.2, zorder=2)
        ax.add_patch(circle_line)
    else:
        # 5-point closed contour (Rectangle)
        gx = [x,   x+w, x+w, x,   x]
        gy = [y,   y,   y+h, y+h, y]
        
        # Fill with transparency
        ax.fill(gx, gy, color=color, alpha=0.5, zorder=1)
        # Edge lines
        ax.plot(gx, gy, color=color, lw=1.2, zorder=2)

    # Label in center
    cx, cy = x + w / 2, y + h / 2
    # Add rotation indicator if applicable
    label = f"{name}"
    if group.get("rotated"):
        label += " (R)"
    ax.text(cx, cy, label, color='white', fontsize=6,
            fontweight='bold', ha='center', va='center', zorder=3,
            bbox=dict(facecolor='#333333', alpha=0.8, edgecolor='none', pad=1))


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

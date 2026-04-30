import matplotlib.pyplot as plt

def get_groups(site_width, site_length, pb_dx=0, pb_dy=0, ct_dx=0, ct_dy=0, adm_dx=0, adm_dy=0):
    """
    Define the 3 main building groups with their dimensions and default positions.
    Positions are calculated based on site dimensions and optional manual offsets.
    """
    # Footprint dimensions (estimated in meters)
    pw_w, pw_h = 120, 80   # Power Block footprint
    ct_w, ct_h = 60,  80   # Cooling Tower footprint
    adm_w, adm_h = 50, 40  # Admin Building footprint

    return [
        {   # Power Block — centered on site
            "name": "Power Block",
            "x": (site_width - pw_w) / 2 + pb_dx,
            "y": (site_length - pw_h) / 2 + pb_dy,
            "width": pw_w, 
            "height": pw_h,
            "color": "#4a90d9",
        },
        {   # Cooling Tower — right edge, vertically centered
            "name": "Cooling Tower",
            "x": site_width - ct_w - 10 + ct_dx,
            "y": (site_length - ct_h) / 2 + ct_dy,
            "width": ct_w, 
            "height": ct_h,
            "color": "#7ed6a0",
        },
        {   # Admin Building — lower-left
            "name": "Admin Building",
            "x": 20 + adm_dx,
            "y": 20 + adm_dy,
            "width": adm_w, 
            "height": adm_h,
            "color": "#f5a623",
        },
    ]

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

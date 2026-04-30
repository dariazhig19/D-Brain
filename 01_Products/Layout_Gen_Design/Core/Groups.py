import matplotlib.pyplot as plt

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

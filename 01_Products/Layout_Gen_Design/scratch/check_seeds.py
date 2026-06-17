import sys
import os
import random
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Core.Layout06 import generate_sketch

print("Checking first 15 seeds:")
for seed in range(15):
    random.seed(seed)
    res = generate_sketch(
        site_w=500, site_l=270, wind_dir="East",
        gate_side="N", gate_ratio=0.4,
        gh_edge="N", gh_ratio=0.6, gh_offset=15,
        bb_edge="S",
        gis_edge="N", gis_ratio=0.9, gis_offset=15,
        water_edge="E", water_ratio=0.2, water_offset=0
    )
    if res:
        admin = next((b for b in res["blocks"] if b["name"] == "Admin Building"), None)
        warehouse = next((b for b in res["blocks"] if b["name"] == "Warehouse"), None)
        print(f"Seed {seed}:")
        if admin:
            print(f"  Admin: x={admin['x']:.1f}, y={admin['y']:.1f}, w={admin['width']:.1f}, h={admin['height']:.1f}")
        if warehouse:
            print(f"  Warehouse: x={warehouse['x']:.1f}, y={warehouse['y']:.1f}, w={warehouse['width']:.1f}, h={warehouse['height']:.1f}")
            
        # Check intersections
        for name, block in [("Admin", admin), ("Warehouse", warehouse)]:
            if block:
                bx0, by0 = block["x"], block["y"]
                bx1, by1 = bx0 + block["width"], by0 + block["height"]
                for i, seg in enumerate(res["rack_segments"]):
                    p1, p2 = seg
                    sxmin, sxmax = min(p1[0], p2[0]), max(p1[0], p2[0])
                    symin, symax = min(p1[1], p2[1]), max(p1[1], p2[1])
                    # Does it overlap?
                    if not (sxmax < bx0 or sxmin > bx1 or symax < by0 or symin > by1):
                        # check if it just touches the boundary
                        if (sxmax == bx0 or sxmin == bx1 or symax == by0 or symin == by1):
                            # just touching is fine, but if it crosses or goes inside:
                            pass
                        else:
                            print(f"  -> INTERSECT: {name} overlaps with rack seg {p1} -> {p2}")
    else:
        print(f"Seed {seed}: Failed to place")

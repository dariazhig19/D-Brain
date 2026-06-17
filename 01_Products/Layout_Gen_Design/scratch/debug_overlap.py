import sys
import os
import random
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Core.Layout06 import _overlaps, pair_min_gap, _overlaps_any, generate_sketch

random.seed(12)
res = generate_sketch(
    site_w=500, site_l=270, wind_dir="East",
    gate_side="N", gate_ratio=0.4,
    gh_edge="N", gh_ratio=0.6, gh_offset=15,
    bb_edge="S",
    gis_edge="N", gis_ratio=0.9, gis_offset=15,
    water_edge="E", water_ratio=0.2, water_offset=0
)

if res:
    print("Placed blocks:")
    placed_dict = {}
    for b in res["blocks"]:
        print(f"  {b['name']}: {b['x']}, {b['y']}, {b['width']}, {b['height']}")
        placed_dict[b["name"]] = (b["x"], b["y"], b["width"], b["height"])
    
    # Check overlap between Admin and Power Block
    admin = placed_dict.get("Admin Building")
    pb = placed_dict.get("Power Block")
    if admin and pb:
        gap = pair_min_gap("Admin Building", "Power Block")
        overlap_direct = _overlaps(admin[0], admin[1], admin[2], admin[3], pb[0], pb[1], pb[2], pb[3], gap)
        print(f"\nOverlap check between Admin and Power Block with gap={gap}:")
        print(f"  _overlaps returned: {overlap_direct}")
        # print conditions
        ax, ay, aw, ah = admin
        bx, by, bw, bh = pb
        c1 = ax + aw + gap <= bx
        c2 = bx + bw + gap <= ax
        c3 = ay + ah + gap <= by
        c4 = by + bh + gap <= ay
        print(f"  Conditions: {c1}, {c2}, {c3}, {c4}")

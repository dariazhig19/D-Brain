import sys
import os
import random
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Core.Layout06 import generate_sketch

random.seed(42)

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
    for b in res["blocks"]:
        print(f"  {b['name']}: x={b['x']:.2f}, y={b['y']:.2f}, w={b['width']:.2f}, h={b['height']:.2f}")
    
    print("\nRack segments:")
    for i, seg in enumerate(res["rack_segments"]):
        p1, p2 = seg
        print(f"  Seg {i}: {p1} -> {p2}")
else:
    print("Sketch generation returned None")

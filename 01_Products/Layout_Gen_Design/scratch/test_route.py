import sys
import os
import random
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# We can dynamically hot-patch or just test if route_between works for seed 8 and seed 1
from Core.Layout06 import generate_sketch

# Let's inspect seed 8
random.seed(8)
res = generate_sketch(
    site_w=500, site_l=270, wind_dir="East",
    gate_side="N", gate_ratio=0.4,
    gh_edge="N", gh_ratio=0.6, gh_offset=15,
    bb_edge="S",
    gis_edge="N", gis_ratio=0.9, gis_offset=15,
    water_edge="E", water_ratio=0.2, water_offset=0
)
if res:
    print("Seed 8:")
    for b in res["blocks"]:
        print(f"  {b['name']}: x={b['x']:.2f}, y={b['y']:.2f}, w={b['width']:.2f}, h={b['height']:.2f}")
    print("\nRack segments:")
    for i, seg in enumerate(res["rack_segments"]):
        p1, p2 = seg
        print(f"  Seg {i}: {p1} -> {p2}")
else:
    print("Seed 8: Failed")

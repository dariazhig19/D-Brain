import sys
import os
import random
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Core.Layout06 import generate_sketch

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
    for b in res["blocks"]:
        print(f"  {b['name']}: x={b['x']}, y={b['y']}, w={b['width']}, h={b['height']}")
    print("\nRing Road:")
    print("  ", res["ring_road"])
    print("\nGate Spur:")
    print("  ", res["gate_spur"])
    print("\nRing Spur:")
    print("  ", res["ring_spur"])
    print("\nRack segments:")
    for i, seg in enumerate(res["rack_segments"]):
        print(f"  Seg {i}: {seg[0]} -> {seg[1]}")
    print("\nOuter Loop:")
    print("  ", res["outer_loop"])
    print("\nAll Segments Cleaned:")
    for i, seg in enumerate(res["all_segments_cleaned"]):
        print(f"  Seg {i}: {seg[0]} -> {seg[1]}")

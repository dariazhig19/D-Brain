import sys
import os
import random
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import Core.Layout06

random.seed(42)
res = Core.Layout06.generate_sketch(
    site_w=500, site_l=270, wind_dir="East",
    gate_side="N", gate_ratio=0.4,
    gh_edge="N", gh_ratio=0.6, gh_offset=15,
    bb_edge="N",
    gis_edge="N", gis_ratio=0.9, gis_offset=15,
    water_edge="E", water_ratio=0.2, water_offset=0
)

if res:
    print("Spine Creation Debug:")
    for k, v in Core.Layout06._last_debug.get("spine_creation", {}).items():
        print(f"  {k}: {v}")
else:
    print("Generation failed")

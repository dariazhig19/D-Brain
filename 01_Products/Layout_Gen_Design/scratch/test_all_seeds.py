import sys
import os
import random
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import Core.Layout06

failures = []
for seed in range(100):
    random.seed(seed)
    res = Core.Layout06.generate_sketch(
        site_w=500, site_l=270, wind_dir="East",
        gate_side="N", gate_ratio=0.4,
        gh_edge="N", gh_ratio=0.6, gh_offset=15,
        bb_edge="S",
        gis_edge="N", gis_ratio=0.9, gis_offset=15,
        water_edge="E", water_ratio=0.2, water_offset=0
    )
    if res:
        spine_debug = Core.Layout06._last_debug.get("spine_creation", {})
        overlap = spine_debug.get("overlap", False)
        spines = spine_debug.get("spine_centerlines", [])
        if not overlap:
            step7_segs = len(spines) - 3
            if step7_segs <= 0:
                failures.append(seed)

print(f"Failed to find Step 7 path in {len(failures)} out of 100 seeds.")
if failures:
    print(f"Failed seeds: {failures}")

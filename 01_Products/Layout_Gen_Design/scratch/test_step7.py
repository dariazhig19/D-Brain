import sys
import os
import random
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Core.Layout06 import generate_sketch

print("Checking Step 7 connections for seeds 0 to 30:")
for seed in range(30):
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
        # Check if we have more than 3 rack segments when is_overlap is False
        # If they overlap, there's no Step 7 A* path, but there is a closest_perp_line.
        # Let's count how many segments we have in rack_segments.
        # For a standard non-overlapping case:
        # best_pb_half (1) + best_ct_half (1) + main_rack (1) = 3 segments.
        # If Step 7 routes a path, it should add 1 or more segments.
        # Let's see if the connection is missing.
        # We can also inspect the debug dict.
        last_debug = res.get("computed_buffers_debug", {})
        # Note: Layout06.py has a global _last_debug where we store details.
        from Core.Layout06 import _last_debug
        spine_debug = _last_debug.get("spine_creation", {})
        overlap = spine_debug.get("overlap", False)
        perp = spine_debug.get("perp_line", None)
        path_added = False
        # Count if there are segments in spine_centerlines besides best_pb_half, best_ct_half, and main_rack
        spines = spine_debug.get("spine_centerlines", [])
        if not overlap:
            # PB half, CT half, main_rack are the first 3.
            # Any additional segments are Step 7 path.
            step7_segs = len(spines) - 3
            print(f"Seed {seed}: Overlap={overlap}, Step 7 path segments={step7_segs}")
        else:
            print(f"Seed {seed}: Overlap={overlap} (perp_line={perp is not None})")
    else:
        print(f"Seed {seed}: Failed to place")

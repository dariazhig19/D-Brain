import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import Core.Layout06 as Layout06
import random

def test():
    success = 0
    total = 20
    for i in range(total):
        random.seed(42 + i)
        sketch = Layout06.generate_sketch(
            sw=500, sl=270, wind_dir="East",
            gate_side="N", gate_ratio=0.4,
            gh_edge="N", gh_ratio=0.6, gh_offset=15,
            bb_edge="N",
            gis_edge="N", gis_ratio=0.9, gis_offset=15,
            water_edge="E", water_ratio=0.2, water_offset=0
        )
        if sketch is not None:
            success += 1
            print(f"Seed {42+i}: SUCCESS")
        else:
            dbg = Layout06._last_debug
            failed_at = dbg.get("failed_at", "?")
            print(f"Seed {42+i}: FAILED at {failed_at}")

    print(f"\nResult: {success}/{total} successful placements.")

if __name__ == "__main__":
    test()

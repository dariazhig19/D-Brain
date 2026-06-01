import sys, random, importlib, math
sys.path.append('.')
import Core.Layout06 as L
importlib.reload(L)

def test():
    random.seed(42)
    r = L.generate_sketch(
        500, 270, 'East',
        gate_side="N", gate_ratio=0.4,
        gh_edge="N", gh_ratio=0.6, gh_offset=15,
        bb_edge="N",
        gis_edge="N", gis_ratio=0.9, gis_offset=15,
        water_edge="E", water_ratio=0.2, water_offset=0
    )
    
    for c in r['loop_connectors']:
        p1, p2 = c
        if abs(p1[1] - p2[1]) < 0.1:
            print(f"  [H] {p1} -> {p2}  len={abs(p1[0]-p2[0])}")
        else:
            print(f"  [V] {p1} -> {p2}  len={abs(p1[1]-p2[1])}")

if __name__ == "__main__":
    test()

import sys, random, importlib
sys.path.append('.')
import Core.Layout06 as L
importlib.reload(L)

random.seed(42)
r = L.generate_sketch(
    500, 270, 'East',
    gate_side="N", gate_ratio=0.4,
    gh_edge="N", gh_ratio=0.6, gh_offset=15,
    bb_edge="N",
    gis_edge="N", gis_ratio=0.9, gis_offset=15,
    water_edge="E", water_ratio=0.2, water_offset=0
)

cleaned = r.get('all_segments_cleaned', [])
connectors = r.get('loop_connectors', [])
final = r.get('road_network_final', [])

print(f"§3.7.D all_segments_cleaned : {len(cleaned)} segs")
print(f"§3.7.E loop_connectors      : {len(connectors)} segs")
print(f"       road_network_final   : {len(final)} segs (merged)")

# Verify no overlap in segment sets
cleaned_set = set(tuple(map(tuple, s)) for s in cleaned)
connector_set = set(tuple(map(tuple, s)) for s in connectors)
print(f"\nOverlap between D and E raw: {len(cleaned_set & connector_set)} (should be 0)")

print("\n§3.7.E connectors:")
for p1, p2 in connectors:
    kind = "H" if abs(p1[1]-p2[1]) < 0.1 else "V"
    length = abs(p1[0]-p2[0]) + abs(p1[1]-p2[1])
    print(f"  [{kind}] {p1} -> {p2}  len={length:.1f}m")

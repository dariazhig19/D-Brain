import sys
sys.path.append('.')
import Core.Layout06 as L
r = L.generate_sketch(500, 270, 'East', gate_side='N', gate_ratio=0.4, gh_edge='N', gh_ratio=0.6, gh_offset=15, bb_edge='N', gis_edge='N', gis_ratio=0.9, gis_offset=15, water_edge='E', water_ratio=0.2, water_offset=0)
h_segs = []
for (ax, ay), (bx, by) in r['all_segments_cleaned']:
    if abs(ay - by) < 0.1: h_segs.append((min(ax, bx), max(ax, bx), ay))

for h in sorted(h_segs, key=lambda x: x[2]):
    print(h)

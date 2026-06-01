import sys, random, importlib, math
sys.path.append('.')
import Core.Layout06 as L

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
    
    # We want to trace the create_perimeter_loop specifically for the Warehouse.
    segs = r['all_segments_cleaned']
    raw_segs = r['group_a_segments_raw'] + r['perimeter_segments_raw']
    
    sw, sl = 500, 270
    TOL = 0.1

    h_segs = []
    v_segs = []
    for (ax, ay), (bx, by) in segs:
        if abs(ay - by) < TOL:
            h_segs.append((min(ax, bx), max(ax, bx), ay))
        elif abs(ax - bx) < TOL:
            v_segs.append((ax, min(ay, by), max(ay, by)))

    raw_h = set()
    raw_v = set()
    for (ax, ay), (bx, by) in raw_segs:
        if abs(ay - by) < TOL:
            raw_h.add((round(min(ax, bx), 1), round(max(ax, bx), 1), round(ay, 1)))
        elif abs(ax - bx) < TOL:
            raw_v.add((round(ax, 1), round(min(ay, by), 1), round(max(ay, by), 1)))

    def _is_original_h(x0, x1, y):
        return (round(x0, 1), round(x1, 1), round(y, 1)) in raw_h

    def _x_ranges_overlap(ax0, ax1, bx0, bx1):
        return min(ax1, bx1) > max(ax0, bx0)

    outer_s = []
    for h in h_segs:
        hx0, hx1, hy = h
        if not _is_original_h(hx0, hx1, hy): continue
        is_s = not any(h2[2] < hy - TOL and _x_ranges_overlap(hx0, hx1, h2[0], h2[1]) for h2 in h_segs)
        if is_s:
            outer_s.append(h)

    print("South Outer Segments:")
    for s in outer_s:
        print("  ", s)
        
    print("\nWarehouse block:")
    for b in r['blocks']:
        if b['name'] == 'Warehouse':
            print(f"  {b['name']}: {b}")
            
    # And buffer:
    from Core.Layout06 import compute_snapped_buffers
    bufs = compute_snapped_buffers(r['blocks'])
    wh_buf = bufs['Warehouse']
    print(f"Warehouse Buffer: x={wh_buf[0]}, y={wh_buf[1]}, w={wh_buf[2]}, h={wh_buf[3]}")
    print(f"  Bottom edge of buffer should be at y={wh_buf[1]}")

if __name__ == "__main__":
    test()

import sys, os, random
sys.path.append(os.path.abspath('.'))

from Core.Layout06 import generate_sketch, _last_debug, compute_unsnapped_buffers

random.seed(43)
res = generate_sketch(
    site_w=500, site_l=270, wind_dir="East",
    gate_side="N", gate_ratio=0.4,
    gh_edge="N", gh_ratio=0.5, gh_offset=0,
    gis_edge="N", gis_ratio=0.8, gis_offset=0,
    water_edge="E", water_ratio=0.2, water_offset=0,
    max_pool=300,
)

if res:
    pb = next(b for b in res["blocks"] if b["name"] == "Power Block")
    pb_x, pb_y, pb_w, pb_h = pb["x"], pb["y"], pb["width"], pb["height"]
    print(f"PB: x={pb_x}, y={pb_y}, w={pb_w}, h={pb_h}")
    print(f"PB spans: x=[{pb_x}, {pb_x+pb_w}], y=[{pb_y}, {pb_y+pb_h}]")

    # Check PB buffer in computed_buffers_debug
    cbufs = res.get("computed_buffers_debug", {})
    pb_buf = cbufs.get("Power Block")
    if pb_buf:
        bx, by, bw, bh = pb_buf
        print(f"\nPB buffer: x={bx}, y={by}, w={bw}, h={bh}")
        print(f"PB buffer spans: x=[{bx}, {bx+bw}], y=[{by}, {by+bh}]")
        print(f"  buffer south edge y={by} vs PB south edge y={pb_y}")
        print(f"  buffer offset south = {pb_y - by}m")
        print(f"  buffer offset north = {(by + bh) - (pb_y + pb_h)}m")
        print(f"  buffer offset west  = {pb_x - bx}m")
        print(f"  buffer offset east  = {(bx + bw) - (pb_x + pb_w)}m")

    # PB rack sides
    dbg = _last_debug
    pb_rack_sides = dbg.get("pb_rack_sides_final")
    print(f"\nPB rack sides from _last_debug: {pb_rack_sides}")
    
    # Also check the placed dict's _pb_rack_sides
    for key in ["_pb_rack_sides"]:
        if key in dbg:
            print(f"  {key}: {dbg[key]}")

    # Outer loop first crossing segment
    outer_loop = res.get("outer_loop", [])
    print(f"\nOuter loop crossing PB segments:")
    for i, seg in enumerate(outer_loop):
        p1, p2 = seg[0], seg[1]
        crosses_pb = False
        if abs(p1[0] - p2[0]) < 0.1:  # vertical
            x = p1[0]
            y_lo, y_hi = min(p1[1], p2[1]), max(p1[1], p2[1])
            if pb_x < x < pb_x + pb_w and y_lo < pb_y + pb_h and y_hi > pb_y:
                crosses_pb = True
        elif abs(p1[1] - p2[1]) < 0.1:  # horizontal
            y = p1[1]
            x_lo, x_hi = min(p1[0], p2[0]), max(p1[0], p2[0])
            if pb_y < y < pb_y + pb_h and x_lo < pb_x + pb_w and x_hi > pb_x:
                crosses_pb = True
        if crosses_pb:
            print(f"  [{i}] ({p1[0]:.1f},{p1[1]:.1f}) -> ({p2[0]:.1f},{p2[1]:.1f})")

    # Ring road
    ring = res.get("ring_road", [])
    print(f"\nRing road: {ring}")
else:
    print("Generation failed")

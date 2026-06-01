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

placed = {b['name']: (b['x'], b['y'], b['width'], b['height']) for b in r['blocks']}
pb = placed["Power Block"]
pb_cx = pb[0] + pb[2]/2
buffers = L.compute_snapped_buffers(placed)

print(f"pb_cx = {pb_cx}")
print()

# Show Admin and WT/WWT buffers
for name in ["Admin Building", "WT/WWT"]:
    b = buffers[name]
    print(f"{name} buffer: x={b[0]}, y={b[1]}, x2={b[0]+b[2]}, y2={b[1]+b[3]}")

print()
print("== Right-group horizontal raw segments ==")
all_raw = r['perimeter_segments_raw'] + r['group_a_segments_raw']
right_h = []
for p1, p2 in all_raw:
    if abs(p1[1] - p2[1]) < 0.1:
        mid_x = (p1[0] + p2[0]) / 2
        if mid_x >= pb_cx:
            right_h.append((p1[1], p1[0], p2[0]))
            print(f"  Y={p1[1]:6.1f}  x=[{p1[0]:.1f} → {p2[0]:.1f}]  midX={mid_x:.1f}")

print()
print("== Sorted by Y desc (sweep order) ==")
right_h.sort(key=lambda t: t[0], reverse=True)
for y, x0, x1 in right_h:
    print(f"  Y={y:6.1f}  x=[{x0:.1f} → {x1:.1f}]")

print()
print("== Cleaned horizontal lines ==")
for p1, p2 in r['all_segments_cleaned']:
    if abs(p1[1] - p2[1]) < 0.1:
        mid_x = (p1[0] + p2[0]) / 2
        side = "LEFT" if mid_x < pb_cx else "RIGHT"
        print(f"  [{side}]  Y={p1[1]:6.1f}  x=[{p1[0]:.1f} → {p2[0]:.1f}]")

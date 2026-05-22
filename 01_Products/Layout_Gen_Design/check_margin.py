import sys, random, importlib
sys.path.append('.')
import Core.Layout06 as L
importlib.reload(L)

random.seed(42)
r = L.generate_sketch(500, 270, 'East')
m = L.BOUNDARY_MARGIN
sw, sl = 500, 270
ANCHORS = {'Gate House', 'GIS', 'RAW Water Tank'}

if r:
    print('Block boundary margins (floated blocks must all be >= 15m):')
    ok = True
    for b in r['blocks']:
        name = b['name']
        x, y, w, h = b['x'], b['y'], b['width'], b['height']
        if name in ANCHORS:
            print(f"  {name} (anchor) -- skip")
            continue
        L_gap = x
        R_gap = sw - x - w
        B_gap = y
        T_gap = sl - y - h
        fail = []
        if L_gap < m: fail.append(f"L={L_gap:.0f}")
        if R_gap < m: fail.append(f"R={R_gap:.0f}")
        if B_gap < m: fail.append(f"B={B_gap:.0f}")
        if T_gap < m: fail.append(f"T={T_gap:.0f}")
        status = "FAIL " + ", ".join(fail) if fail else "OK"
        print(f"  {name}: L={L_gap:.0f} R={R_gap:.0f} B={B_gap:.0f} T={T_gap:.0f}  [{status}]")
        if fail:
            ok = False
    print("ALL OK" if ok else "VIOLATIONS FOUND")
else:
    print("FAILED to generate layout")

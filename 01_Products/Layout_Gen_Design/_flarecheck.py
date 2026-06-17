"""Throwaway: confirm Flare excluded from perimeter union but keeps 6m access."""
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from Core.Layout06 import generate_sketch

SITE = (500, 270, "East")
KW = dict(gate_side="N", gate_ratio=0.4, gh_edge="N", gh_ratio=0.6, gh_offset=15,
          bb_edge="N", gis_edge="N", gis_ratio=0.9, gis_offset=15,
          water_edge="E", water_ratio=0.2, water_offset=0)
SEEDS = list(range(1, 41))

def seg_hits_box(seg, box):
    (x1, y1), (x2, y2) = seg[0], seg[1]
    bx0, by0, bx1, by1 = box
    sxmin, sxmax = min(x1, x2), max(x1, x2)
    symin, symax = min(y1, y2), max(y1, y2)
    return not (sxmax < bx0 or sxmin > bx1 or symax < by0 or symin > by1)

errors = peri_near_flare = flare_access = ok = 0
for s in SEEDS:
    random.seed(s)
    try:
        sk = generate_sketch(*SITE, **KW)
    except Exception as e:
        errors += 1; print("ERR seed", s, e); continue
    if not sk:
        continue
    ok += 1
    fb = next((b for b in sk["blocks"] if b["name"] == "Flare"), None)
    if not fb:
        continue
    # Flare's old 16m perimeter buffer box
    fx, fy = fb["x"], fb["y"]; fw, fh = fb["width"], fb["height"]
    box = (fx-16, fy-16, fx+fw+16, fy+fh+16)
    peri = list(sk.get("outer_loop", []))
    if any(seg_hits_box(seg, box) for seg in peri):
        peri_near_flare += 1
    if sk.get("group_b_points", {}).get("Flare"):
        flare_access += 1

tag = sys.argv[1] if len(sys.argv) > 1 else "out"
print(f"[{tag}] layouts={ok}  errors={errors}  perimeter-near-Flare={peri_near_flare}  Flare-6m-access={flare_access}")

# dump per-seed outer_loop signature to detect ANY change before/after
import json
sigs = {}
for s in SEEDS:
    random.seed(s)
    sk = generate_sketch(*SITE, **KW)
    if sk:
        sigs[s] = [[[round(c, 2) for c in p] for p in seg] for seg in sk.get("outer_loop", [])]
json.dump(sigs, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), f"_loop_{tag}.json"), "w"), default=str)

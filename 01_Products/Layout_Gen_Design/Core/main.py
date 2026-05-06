import random
import math
from Core.Groups import get_groups
from Core.Rules import evaluate_all

# Building footprints (must match Groups.py)
PB_W, PB_H   = 120, 80
CT_W, CT_H   = 60,  80
ADM_W, ADM_H = 50,  40


def _place_pb(site_width, site_length):
    """Power Block: near center with random ±25% variation."""
    cx = (site_width  - PB_W) / 2
    cy = (site_length - PB_H) / 2
    x = cx + random.uniform(-site_width  * 0.25, site_width  * 0.25)
    y = cy + random.uniform(-site_length * 0.25, site_length * 0.25)
    return max(5, min(site_width  - PB_W - 5, x)), \
           max(5, min(site_length - PB_H - 5, y))


def _place_ct(site_width, site_length, wind_dir):
    """Cooling Tower: constrained to windward zone (within 25 m of windward edge)."""
    margin = 5
    depth  = random.uniform(5, 25)      # distance from windward edge

    if wind_dir == "East":
        x = site_width  - CT_W - depth
        y = random.uniform(margin, site_length - CT_H - margin)
    elif wind_dir == "West":
        x = depth
        y = random.uniform(margin, site_length - CT_H - margin)
    elif wind_dir == "North":
        x = random.uniform(margin, site_width - CT_W - margin)
        y = site_length - CT_H - depth
    else:   # South
        x = random.uniform(margin, site_width - CT_W - margin)
        y = depth

    return max(0, min(site_width  - CT_W, x)), \
           max(0, min(site_length - CT_H, y))


def _place_adm(site_width, site_length, attempts=400):
    """Admin: ≥20 m setback AND within 50 m of Gate House (site_width/2, 0)."""
    gate_x, gate_y = site_width / 2, 0.0
    for _ in range(attempts):
        x = random.uniform(20, site_width  - ADM_W - 20)
        y = random.uniform(20, min(site_length - ADM_H - 20, 65))
        cx, cy = x + ADM_W / 2, y + ADM_H / 2
        if math.dist((cx, cy), (gate_x, gate_y)) <= 50:
            return x, y
    # fallback: bottom-center
    return max(20, site_width / 2 - ADM_W / 2), 20


def generate_layouts(site_width, site_length, wind_dir,
                     n_results=10, min_rules_passing=3, max_pool=3000):
    """
    Constrained random placement engine.

    Returns up to n_results layout dicts, sorted by total_penalty (lowest first).
    Each dict: {pb_x, pb_y, ct_x, ct_y, adm_x, adm_y, groups, scoring}
    """
    candidates = []

    for _ in range(max_pool):
        pb_x, pb_y  = _place_pb(site_width, site_length)
        ct_x, ct_y  = _place_ct(site_width, site_length, wind_dir)
        adm_x, adm_y = _place_adm(site_width, site_length)

        groups  = get_groups(site_width, site_length,
                             pb_x=pb_x, pb_y=pb_y,
                             ct_x=ct_x, ct_y=ct_y,
                             adm_x=adm_x, adm_y=adm_y)
        scoring = evaluate_all(groups, site_width, site_length, wind_dir)
        passing = sum(1 for r in scoring["results"] if r["passed"])

        if passing >= min_rules_passing:
            candidates.append({
                "pb_x": pb_x, "pb_y": pb_y,
                "ct_x": ct_x, "ct_y": ct_y,
                "adm_x": adm_x, "adm_y": adm_y,
                "groups":  groups,
                "scoring": scoring,
            })

        if len(candidates) >= n_results * 15:
            break

    candidates.sort(key=lambda c: c["scoring"]["total_penalty"])

    # Diversity filter: keep results that are meaningfully different
    diverse = []
    for c in candidates:
        if len(diverse) >= n_results:
            break
        too_close = False
        for d in diverse:
            if (abs(c["pb_x"]  - d["pb_x"])  < 10 and
                abs(c["ct_x"]  - d["ct_x"])  < 10 and
                abs(c["adm_x"] - d["adm_x"]) < 10):
                too_close = True
                break
        if not too_close:
            diverse.append(c)

    # If diversity filter left too few, pad with next-best
    if len(diverse) < n_results:
        used_penalties = {d["scoring"]["total_penalty"] for d in diverse}
        for c in candidates:
            if len(diverse) >= n_results:
                break
            if c["scoring"]["total_penalty"] not in used_penalties:
                diverse.append(c)
                used_penalties.add(c["scoring"]["total_penalty"])

    diverse.sort(key=lambda c: c["scoring"]["total_penalty"])
    return diverse[:n_results]

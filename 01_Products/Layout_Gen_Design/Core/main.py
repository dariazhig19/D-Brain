import random
import math
from Core.Groups import get_all_groups, get_all_racks, FOOTPRINTS, RACK_WIDTHS
from Core.Rules import evaluate_all_v2

# ── Footprint shortcuts ───────────────────────────────────────────────────

_FP = FOOTPRINTS  # {name: (width, height)}


# ── Placement helpers ─────────────────────────────────────────────────────

def _clamp(val, lo, hi):
    return max(lo, min(hi, val))


def _rand_pos(site_w, site_l, w, h, margin=5):
    """Random position within site boundaries with a minimum margin."""
    x = random.uniform(margin, max(margin, site_w - w - margin))
    y = random.uniform(margin, max(margin, site_l - h - margin))
    return x, y


# ── Overlap detection ─────────────────────────────────────────────────────

_OVERLAP_GAP = 2  # minimum gap (metres) between any two buildings


def _rects_overlap(x1, y1, w1, h1, x2, y2, w2, h2, gap=_OVERLAP_GAP):
    """Return True if two rectangles overlap (with a minimum gap buffer)."""
    return not (x1 + w1 + gap <= x2 or
                x2 + w2 + gap <= x1 or
                y1 + h1 + gap <= y2 or
                y2 + h2 + gap <= y1)


def _has_any_overlap(positions):
    """
    Check if any pair of placed rectangles overlaps.
    positions: dict {name: (x, y)}  — uses FOOTPRINTS for width/height.
    Returns True if ANY overlap exists.
    """
    items = []
    for name, (x, y) in positions.items():
        if name in _FP:
            w, h = _FP[name]
            items.append((x, y, w, h))
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if _rects_overlap(*items[i], *items[j]):
                return True
    return False


def _line_intersects_rect(p1, p2, rx, ry, rw, rh):
    """Check if line segment p1-p2 intersects rectangle (rx, ry, rw, rh)."""
    min_x, max_x = min(p1[0], p2[0]), max(p1[0], p2[0])
    min_y, max_y = min(p1[1], p2[1]), max(p1[1], p2[1])
    
    if max_x < rx or min_x > rx + rw: return False
    if max_y < ry or min_y > ry + rh: return False

    def ccw(A, B, C):
        return (C[1]-A[1]) * (B[0]-A[0]) > (B[1]-A[1]) * (C[0]-A[0])
        
    def intersect(A, B, C, D):
        return ccw(A,C,D) != ccw(B,C,D) and ccw(A,B,C) != ccw(A,B,D)

    A, B = p1, p2
    rect_pts = [(rx, ry), (rx+rw, ry), (rx+rw, ry+rh), (rx, ry+rh)]
    for i in range(4):
        if intersect(A, B, rect_pts[i], rect_pts[(i+1)%4]):
            return True
            
    # Also check if fully inside
    if rx <= p1[0] <= rx + rw and ry <= p1[1] <= ry + rh:
        return True
        
    return False


# ── Per-group placement strategies ────────────────────────────────────────

def _place_power_block(sw, sl):
    """Power Block: near center with ±25% random variation."""
    w, h = _FP["Power Block"]
    cx = (sw - w) / 2 + random.uniform(-sw * 0.15, sw * 0.15)
    cy = (sl - h) / 2 + random.uniform(-sl * 0.15, sl * 0.15)
    return _clamp(cx, 5, sw - w - 5), _clamp(cy, 5, sl - h - 5)


def _place_cooling_tower(sw, sl, wind_dir):
    """Cooling Tower: constrained to windward zone (within 25 m of windward edge)."""
    w, h = _FP["Cooling Tower"]
    margin = 5
    depth = random.uniform(5, 25)

    if wind_dir == "East":
        x = sw - w - depth
        y = random.uniform(margin, sl - h - margin)
    elif wind_dir == "West":
        x = depth
        y = random.uniform(margin, sl - h - margin)
    elif wind_dir == "North":
        x = random.uniform(margin, sw - w - margin)
        y = sl - h - depth
    else:  # South
        x = random.uniform(margin, sw - w - margin)
        y = depth

    return _clamp(x, 0, sw - w), _clamp(y, 0, sl - h)


def _place_admin(sw, sl):
    """Admin: ≥ 20 m setback AND within 50 m of Gate House (sw/2, 0)."""
    w, h = _FP["Admin Building"]
    gate_x, gate_y = sw / 2, 0.0
    for _ in range(400):
        x = random.uniform(20, sw - w - 20)
        y = random.uniform(20, min(sl - h - 20, 65))
        cx, cy = x + w / 2, y + h / 2
        if math.dist((cx, cy), (gate_x, gate_y)) <= 50:
            return x, y
    return max(20, sw / 2 - w / 2), 20


def _place_gate_house(sw, sl):
    """Gate House: on bottom boundary, random horizontal position."""
    w, h = _FP["Gate House"]
    x = random.uniform(sw * 0.3, sw * 0.7 - w)
    return x, 0  # sits on the bottom edge





def _place_lpg(sw, sl):
    """LPG/Metering: setback ≥ 10 m, away from center (corner placement)."""
    w, h = _FP["LPG/Metering"]
    margin = 10
    # Prefer corners
    corner = random.choice(["top-left", "top-right", "bottom-left", "bottom-right"])
    if corner == "top-left":
        x, y = margin, sl - h - margin
    elif corner == "top-right":
        x, y = sw - w - margin, sl - h - margin
    elif corner == "bottom-left":
        x, y = margin, margin
    else:
        x, y = sw - w - margin, margin
    # Add some randomness
    x += random.uniform(-5, 5)
    y += random.uniform(-5, 5)
    return _clamp(x, margin, sw - w - margin), _clamp(y, margin, sl - h - margin)


def _place_flare(sw, sl, wind_dir):
    """Flare: on windward edge, like cooling tower but at the corner."""
    w, h = _FP["Flare"]
    margin = 5
    depth = random.uniform(5, 25)

    if wind_dir == "East":
        x = sw - w - depth
        y = random.choice([random.uniform(margin, margin + 40),
                           random.uniform(sl - h - 40, sl - h - margin)])
    elif wind_dir == "West":
        x = depth
        y = random.choice([random.uniform(margin, margin + 40),
                           random.uniform(sl - h - 40, sl - h - margin)])
    elif wind_dir == "North":
        y = sl - h - depth
        x = random.choice([random.uniform(margin, margin + 40),
                           random.uniform(sw - w - 40, sw - w - margin)])
    else:
        y = depth
        x = random.choice([random.uniform(margin, margin + 40),
                           random.uniform(sw - w - 40, sw - w - margin)])

    return _clamp(x, margin, sw - w - margin), _clamp(y, margin, sl - h - margin)


def _place_wt_wwt(sw, sl, wind_dir):
    """WT/WWT: setback ≥ 10 m, prefer downwind side."""
    w, h = _FP["WT/WWT"]
    margin = 10
    # Place on the opposite side of wind direction (downwind)
    if wind_dir == "East":
        x = random.uniform(margin, sw * 0.3)
    elif wind_dir == "West":
        x = random.uniform(sw * 0.7 - w, sw - w - margin)
    else:
        x = random.uniform(margin, sw - w - margin)

    if wind_dir == "North":
        y = random.uniform(margin, sl * 0.3)
    elif wind_dir == "South":
        y = random.uniform(sl * 0.7 - h, sl - h - margin)
    else:
        y = random.uniform(margin, sl - h - margin)

    return _clamp(x, margin, sw - w - margin), _clamp(y, margin, sl - h - margin)


def _place_water(sw, sl, ww_x, ww_y):
    """Water: near WT/WWT, within 80 m but at least 10 m away."""
    w, h = _FP["Water"]
    ww_w, ww_h = _FP["WT/WWT"]
    margin = 10
    for _ in range(200):
        x = ww_x + random.uniform(-60, 60)
        y = ww_y + random.uniform(-60, 60)
        x = _clamp(x, margin, sw - w - margin)
        y = _clamp(y, margin, sl - h - margin)
        # Check distance
        cx1, cy1 = x + w / 2, y + h / 2
        cx2, cy2 = ww_x + ww_w / 2, ww_y + ww_h / 2
        dist = math.dist((cx1, cy1), (cx2, cy2))
        if 10 <= dist <= 80:
            return x, y
    # Fallback: next to WT/WWT
    return _clamp(ww_x + ww_w + 10, margin, sw - w - margin), \
           _clamp(ww_y, margin, sl - h - margin)


# ── Rack placement ────────────────────────────────────────────────────────

def _place_racks(groups):
    """Generate rack segments connecting related groups."""
    by_name = {g["name"]: g for g in groups}

    def _closest_points(g1, g2):
        l1, r1 = g1["x"], g1["x"] + g1["width"]
        b1, t1 = g1["y"], g1["y"] + g1["height"]
        l2, r2 = g2["x"], g2["x"] + g2["width"]
        b2, t2 = g2["y"], g2["y"] + g2["height"]

        if r1 <= l2:   px1, px2 = r1, l2
        elif r2 <= l1: px1, px2 = l1, r2
        else:          px1 = px2 = (max(l1, l2) + min(r1, r2)) / 2

        if t1 <= b2:   py1, py2 = t1, b2
        elif t2 <= b1: py1, py2 = b1, t2
        else:          py1 = py2 = (max(b1, b2) + min(t1, t2)) / 2

        return (px1, py1), (px2, py2)

    def segment(name1, name2):
        g1 = by_name.get(name1)
        g2 = by_name.get(name2)
        if g1 and g2:
            return _closest_points(g1, g2)
        return None

    # Pipe Rack: Power Block <-> Cooling Tower, LPG/Metering, WT/WWT
    pipe_rack = [
        segment("Power Block", "Cooling Tower"),
        segment("Power Block", "LPG/Metering"),
        segment("Power Block", "WT/WWT"),
    ]

    # Main Rack: Power Block <-> Admin Building
    main_rack = [
        segment("Power Block", "Admin Building"),
    ]

    # Utility Rack: WT/WWT <-> Water, Cooling Tower
    utility_rack = [
        segment("WT/WWT", "Water"),
        segment("WT/WWT", "Cooling Tower"),
    ]

    return {
        "Pipe Rack":    [s for s in pipe_rack if s],
        "Main Rack":    [s for s in main_rack if s],
        "Utility Rack": [s for s in utility_rack if s],
    }


# ── Main generator ────────────────────────────────────────────────────────

def generate_layouts(site_width, site_length, wind_dir,
                     n_results=10, min_rules_passing=10, max_pool=3000):
    """
    Constrained random placement engine for all 12 groups (Phase 04).

    Returns up to n_results layout dicts, sorted by total_penalty (lowest first).
    Each dict: {positions, rack_endpoints, groups, racks, scoring}
    """
    candidates = []

    for _ in range(max_pool):
        # Place all 9 rectangular groups
        pb_x, pb_y     = _place_power_block(site_width, site_length)
        ct_x, ct_y     = _place_cooling_tower(site_width, site_length, wind_dir)
        adm_x, adm_y   = _place_admin(site_width, site_length)
        gh_x, gh_y     = _place_gate_house(site_width, site_length)
        lpg_x, lpg_y   = _place_lpg(site_width, site_length)
        fl_x, fl_y     = _place_flare(site_width, site_length, wind_dir)
        ww_x, ww_y     = _place_wt_wwt(site_width, site_length, wind_dir)
        wa_x, wa_y     = _place_water(site_width, site_length, ww_x, ww_y)

        positions = {
            "Power Block":    (pb_x, pb_y),
            "Cooling Tower":  (ct_x, ct_y),
            "Admin Building": (adm_x, adm_y),
            "Gate House":     (gh_x, gh_y),
            "LPG/Metering":   (lpg_x, lpg_y),
            "Flare":          (fl_x, fl_y),
            "WT/WWT":         (ww_x, ww_y),
            "Water":          (wa_x, wa_y),
        }

        # Reject if any buildings overlap
        if _has_any_overlap(positions):
            continue

        groups = get_all_groups(site_width, site_length, positions=positions)

        # Place racks based on group positions
        rack_segments = _place_racks(groups)
        racks = get_all_racks(groups, rack_segments=rack_segments)

        # Reject if racks intersect any building (shrink building by 1m buffer to allow edge connection)
        overlap_found = False
        for rack in racks:
            for p1, p2 in rack["segments"]:
                for g in groups:
                    if _line_intersects_rect(p1, p2, g["x"]+1, g["y"]+1, g["width"]-2, g["height"]-2):
                        overlap_found = True
                        break
                if overlap_found: break
            if overlap_found: break
            
        if overlap_found:
            continue

        # Score
        scoring = evaluate_all_v2(groups, racks, site_width, site_length, wind_dir)
        passing = sum(1 for r in scoring["results"] if r["passed"])

        if passing >= min_rules_passing:
            candidates.append({
                "positions":      positions,
                "rack_segments":  rack_segments,
                "groups":         groups,
                "racks":          racks,
                "scoring":        scoring,
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
            diffs = [abs(c["positions"][k][0] - d["positions"][k][0]) for k in c["positions"]]
            if all(diff < 10 for diff in diffs):
                too_close = True
                break
        if not too_close:
            diverse.append(c)

    # Pad if diversity filter was too strict
    if len(diverse) < n_results:
        for c in candidates:
            if len(diverse) >= n_results:
                break
            if c not in diverse:
                diverse.append(c)

    diverse.sort(key=lambda c: c["scoring"]["total_penalty"])
    return diverse[:n_results]

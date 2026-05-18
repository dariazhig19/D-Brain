import random
import math
from Core.Groups import get_all_groups, get_all_racks, FOOTPRINTS, RACK_WIDTHS, compute_gate_point
from Core.Roads import build_road_network, ROAD_INNER_EDGE, MIN_BUILDING_FROM_BOUNDARY
from Core.Rules import evaluate_all_v2

# ── Footprint shortcuts ───────────────────────────────────────────────────

_FP = FOOTPRINTS  # {name: (width, height)}


# ── Placement helpers ─────────────────────────────────────────────────────

def _clamp(val, lo, hi):
    return max(lo, min(hi, val))


def _rand_pos(site_w, site_l, w, h, margin=15):
    """Random position within site boundaries with road-aware margin."""
    x = random.uniform(margin, max(margin, site_w - w - margin))
    y = random.uniform(margin, max(margin, site_l - h - margin))
    return x, y


# ── Rotation helpers ──────────────────────────────────────────────────────

def _dims(name, rotated):
    """Return (w, h) for a footprint, swapped if rotated 90°."""
    w, h = _FP[name]
    return (h, w) if rotated else (w, h)


def _maybe_rotate(name):
    """Random 0°/90° flag. Square footprints always return False (no-op)."""
    w, h = _FP[name]
    if w == h:
        return False
    return random.random() < 0.5


def _pos_xy(val):
    """Extract (x, y) from a placed-entry tuple (handles 2- or 3-tuple)."""
    return val[0], val[1]


def _pos_rot(val):
    """Extract rotation flag from a placed-entry tuple (default False)."""
    return val[2] if len(val) >= 3 else False


# ── Overlap detection ─────────────────────────────────────────────────────

_OVERLAP_GAP = 1  # minimum gap (metres) between any two buildings (reduced for tight sites)


def _rects_overlap(x1, y1, w1, h1, x2, y2, w2, h2, gap=_OVERLAP_GAP):
    """Return True if two rectangles overlap (with a minimum gap buffer)."""
    return not (x1 + w1 + gap <= x2 or
                x2 + w2 + gap <= x1 or
                y1 + h1 + gap <= y2 or
                y2 + h2 + gap <= y1)


def _has_any_overlap(positions):
    """
    Check if any pair of placed rectangles overlaps.
    positions: dict {name: (x, y) or (x, y, rotated)}  — uses FOOTPRINTS for width/height.
    Returns True if ANY overlap exists.
    """
    items = []
    for name, val in positions.items():
        if name in _FP:
            x, y = _pos_xy(val)
            w, h = _dims(name, _pos_rot(val))
            items.append((x, y, w, h))
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if _rects_overlap(*items[i], *items[j]):
                return True
    return False


def _overlaps_road(x, y, w, h, site_w, site_l, road_inner=ROAD_INNER_EDGE):
    """Check if a building overlaps with the perimeter road corridor.
    Road corridor is between ROAD_SETBACK and ROAD_INNER_EDGE from each boundary.
    Returns True if any part of the building is inside the road corridor.
    """
    # Building must be fully inside the inner road rectangle
    if x < road_inner or y < road_inner:
        return True
    if x + w > site_w - road_inner or y + h > site_l - road_inner:
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


# ── Per-group placement strategies (Phase 05) ─────────────────────────────
# Placement order:
#   1. Gate House (FIXED, North Center)
#   2. GIS (FIXED, North-East)
#   3. Power Block (center, minimal jitter)
#   4. Admin Building (near GH + PB)
#   5. Cooling Tower (leeward edge)
#   6. WT/WWT (leeward, setback)
#   7. Water (near WT/WWT)
#   8. Flare (leeward corner)
#   9. LPG/Metering (corner, setback)
#  10. Warehouse (available space)

_MARGIN = MIN_BUILDING_FROM_BOUNDARY  # 15m from boundary (past the road)


def _place_gate_house(sw, sl, gate_side="N", gate_ratio=0.5):
    """Gate House: placed adjacent to the site gate, just inside the boundary.

    The gate is the physical entry point on the plot boundary. Gate House
    sits flush with the boundary, centered on the gate position.

    Args:
        sw, sl:     site width and length in metres.
        gate_side:  "N" | "S" | "E" | "W" — which boundary edge the gate is on.
        gate_ratio: 0.0–1.0 position along that edge (0.5 = center).
    """
    w, h = _FP["Gate House"]
    gate_x, gate_y = compute_gate_point(gate_side, gate_ratio, sw, sl)

    if gate_side == "N":
        x = _clamp(gate_x - w / 2, 0, sw - w)
        y = sl - h
    elif gate_side == "S":
        x = _clamp(gate_x - w / 2, 0, sw - w)
        y = 0
    elif gate_side == "E":
        x = sw - w
        y = _clamp(gate_y - h / 2, 0, sl - h)
    elif gate_side == "W":
        x = 0
        y = _clamp(gate_y - h / 2, 0, sl - h)
    else:
        raise ValueError(f"gate_side must be N/S/E/W, got {gate_side!r}")
    return x, y, False


def _place_gis(sw, sl, corner="NE"):
    """GIS: FIXED at chosen corner with road-margin clearance. Rotation fixed.

    corner: "NE" | "NW" | "SE" | "SW". Default "NE".
    """
    w, h = _FP["GIS"]
    if corner == "NE":
        x, y = sw - w - _MARGIN, sl - h - _MARGIN
    elif corner == "NW":
        x, y = _MARGIN,           sl - h - _MARGIN
    elif corner == "SE":
        x, y = sw - w - _MARGIN, _MARGIN
    elif corner == "SW":
        x, y = _MARGIN,           _MARGIN
    else:
        raise ValueError(f"gis_corner must be NE/NW/SE/SW, got {corner!r}")
    return x, y, False


def _place_power_block(sw, sl):
    """Power Block: near center with ±5% random variation (tight site).
    Square footprint, so rotation is a no-op."""
    w, h = _FP["Power Block"]
    cx = (sw - w) / 2 + random.uniform(-sw * 0.05, sw * 0.05)
    cy = (sl - h) / 2 + random.uniform(-sl * 0.05, sl * 0.05)
    return _clamp(cx, _MARGIN, sw - w - _MARGIN), _clamp(cy, _MARGIN, sl - h - _MARGIN), False


def _place_admin(sw, sl, gh_x, gh_y, pb_x, pb_y):
    """Admin: near Gate House AND Power Block (north zone, center-ish)."""
    rotated = _maybe_rotate("Admin Building")
    w, h = _dims("Admin Building", rotated)
    pb_w, pb_h = _FP["Power Block"]   # square
    gh_w, gh_h = _FP["Gate House"]    # square
    gh_cx, gh_cy = gh_x + gh_w / 2, gh_y + gh_h / 2
    pb_cx, pb_cy = pb_x + pb_w / 2, pb_y + pb_h / 2

    for _ in range(500):
        # Search near the north zone, between GH and PB
        x = random.uniform(_MARGIN, sw - w - _MARGIN)
        y = random.uniform(pb_y + pb_h + 5, sl - h - _MARGIN)
        cx, cy = x + w / 2, y + h / 2
        d_gh = math.dist((cx, cy), (gh_cx, gh_cy))
        d_pb = math.dist((cx, cy), (pb_cx, pb_cy))
        if d_gh <= 80 and d_pb <= 120:
            return x, y, rotated
    # Fallback: just above Power Block
    return (_clamp(pb_x + pb_w / 2 - w / 2, _MARGIN, sw - w - _MARGIN),
            _clamp(pb_y + pb_h + 10, _MARGIN, sl - h - _MARGIN),
            rotated)


def _place_cooling_tower(sw, sl, wind_dir):
    """Cooling Tower: constrained to leeward (downwind) zone.
    Native footprint is 40w x 183h — very tall and narrow. May rotate 90°.
    """
    rotated = _maybe_rotate("Cooling Tower")
    w, h = _dims("Cooling Tower", rotated)
    depth = random.uniform(_MARGIN, _MARGIN + 15)

    # Leeward = opposite of wind direction
    if wind_dir == "East":
        x = depth   # left side (downwind)
        y = random.uniform(_MARGIN, max(_MARGIN, sl - h - _MARGIN))
    elif wind_dir == "West":
        x = sw - w - depth  # right side (downwind)
        y = random.uniform(_MARGIN, max(_MARGIN, sl - h - _MARGIN))
    elif wind_dir == "North":
        x = random.uniform(_MARGIN, max(_MARGIN, sw - w - _MARGIN))
        y = depth  # bottom side (downwind)
    else:  # South
        x = random.uniform(_MARGIN, max(_MARGIN, sw - w - _MARGIN))
        y = sl - h - depth  # top side (downwind)

    return (_clamp(x, _MARGIN, sw - w - _MARGIN),
            _clamp(y, _MARGIN, max(_MARGIN, sl - h - _MARGIN)),
            rotated)


def _place_wt_wwt(sw, sl, wind_dir):
    """WT/WWT: setback ≥ 15 m, prefer downwind side. May rotate 90°."""
    rotated = _maybe_rotate("WT/WWT")
    w, h = _dims("WT/WWT", rotated)
    # Place on the opposite side of wind direction (downwind)
    if wind_dir == "East":
        x = random.uniform(_MARGIN, sw * 0.3)
    elif wind_dir == "West":
        x = random.uniform(sw * 0.7 - w, sw - w - _MARGIN)
    else:
        x = random.uniform(_MARGIN, sw - w - _MARGIN)

    if wind_dir == "North":
        y = random.uniform(_MARGIN, sl * 0.3)
    elif wind_dir == "South":
        y = random.uniform(sl * 0.7 - h, sl - h - _MARGIN)
    else:
        y = random.uniform(_MARGIN, sl - h - _MARGIN)

    return (_clamp(x, _MARGIN, sw - w - _MARGIN),
            _clamp(y, _MARGIN, sl - h - _MARGIN),
            rotated)


def _place_water(sw, sl, ww_x, ww_y, ww_rotated):
    """Water: near WT/WWT, adjacent but non-overlapping. Water is square (no rotation)."""
    w, h = _FP["Water"]   # square
    ww_w, ww_h = _dims("WT/WWT", ww_rotated)
    # Try placing adjacent to WT/WWT (right, left, top, bottom)
    candidates = [
        (ww_x + ww_w + 5, ww_y),              # right of WT/WWT
        (ww_x - w - 5, ww_y),                  # left of WT/WWT
        (ww_x, ww_y + ww_h + 5),               # above WT/WWT
        (ww_x, ww_y - h - 5),                  # below WT/WWT
        (ww_x + ww_w + 5, ww_y + ww_h - h),    # right-top aligned
    ]
    for cx, cy in candidates:
        cx = _clamp(cx, _MARGIN, sw - w - _MARGIN)
        cy = _clamp(cy, _MARGIN, sl - h - _MARGIN)
        # Verify non-overlap with WT/WWT
        if not _rects_overlap(cx, cy, w, h, ww_x, ww_y, ww_w, ww_h, gap=3):
            return cx, cy, False
    # Fallback with randomness
    for _ in range(200):
        x = ww_x + random.uniform(-80, 80)
        y = ww_y + random.uniform(-80, 80)
        x = _clamp(x, _MARGIN, sw - w - _MARGIN)
        y = _clamp(y, _MARGIN, sl - h - _MARGIN)
        if not _rects_overlap(x, y, w, h, ww_x, ww_y, ww_w, ww_h, gap=3):
            return x, y, False
    # Last resort
    return (_clamp(ww_x + ww_w + 10, _MARGIN, sw - w - _MARGIN),
            _clamp(ww_y, _MARGIN, sl - h - _MARGIN),
            False)


def _place_flare(sw, sl, wind_dir):
    """Flare: on leeward edge, preferably in a corner. 40x40 square (no rotation)."""
    w, h = _FP["Flare"]
    depth = random.uniform(_MARGIN, _MARGIN + 15)

    # Leeward corner placement
    if wind_dir == "East":
        x = depth
        y = random.choice([random.uniform(_MARGIN, _MARGIN + 30),
                           random.uniform(sl - h - 30, sl - h - _MARGIN)])
    elif wind_dir == "West":
        x = sw - w - depth
        y = random.choice([random.uniform(_MARGIN, _MARGIN + 30),
                           random.uniform(sl - h - 30, sl - h - _MARGIN)])
    elif wind_dir == "North":
        y = depth
        x = random.choice([random.uniform(_MARGIN, _MARGIN + 30),
                           random.uniform(sw - w - 30, sw - w - _MARGIN)])
    else:  # South
        y = sl - h - depth
        x = random.choice([random.uniform(_MARGIN, _MARGIN + 30),
                           random.uniform(sw - w - 30, sw - w - _MARGIN)])

    return _clamp(x, _MARGIN, sw - w - _MARGIN), _clamp(y, _MARGIN, sl - h - _MARGIN), False


def _place_lpg(sw, sl):
    """LPG/Metering: setback ≥ 15 m, corner placement. May rotate 90°."""
    rotated = _maybe_rotate("LPG/Metering")
    w, h = _dims("LPG/Metering", rotated)
    # Prefer corners
    corner = random.choice(["top-left", "top-right", "bottom-left", "bottom-right"])
    if corner == "top-left":
        x, y = _MARGIN, sl - h - _MARGIN
    elif corner == "top-right":
        x, y = sw - w - _MARGIN, sl - h - _MARGIN
    elif corner == "bottom-left":
        x, y = _MARGIN, _MARGIN
    else:
        x, y = sw - w - _MARGIN, _MARGIN
    # Add some randomness
    x += random.uniform(-5, 5)
    y += random.uniform(-5, 5)
    return (_clamp(x, _MARGIN, sw - w - _MARGIN),
            _clamp(y, _MARGIN, sl - h - _MARGIN),
            rotated)


def _place_warehouse(sw, sl, placed_positions):
    """Warehouse: find available space, avoid overlaps with placed buildings.
    May rotate 90°."""
    for _ in range(500):
        rotated = _maybe_rotate("Warehouse")
        w, h = _dims("Warehouse", rotated)
        x = random.uniform(_MARGIN, sw - w - _MARGIN)
        y = random.uniform(_MARGIN, sl - h - _MARGIN)
        # Check overlap with all already-placed buildings
        overlap = False
        for name, pval in placed_positions.items():
            if name in _FP:
                px, py = _pos_xy(pval)
                pw, ph = _dims(name, _pos_rot(pval))
                if _rects_overlap(x, y, w, h, px, py, pw, ph, gap=5):
                    overlap = True
                    break
        if not overlap:
            return x, y, rotated
    # Fallback: bottom-left, unrotated
    return _MARGIN, _MARGIN, False


# ── Rack placement ────────────────────────────────────────────────────────

def _place_racks(groups):
    """Generate rack segments connecting related groups (Phase 05)."""
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

    # Cable Tunnel: GIS <-> Power Block
    cable_tunnel = [
        segment("GIS", "Power Block"),
    ]

    return {
        "Pipe Rack":    [s for s in pipe_rack if s],
        "Main Rack":    [s for s in main_rack if s],
        "Utility Rack": [s for s in utility_rack if s],
        "Cable Tunnel": [s for s in cable_tunnel if s],
    }

# ── Collision-aware placement ─────────────────────────────────────────────
def _try_place_collision_aware(sw, sl, name, placed, place_fn, max_attempts=200):
    """Try to place a building using place_fn, checking against already-placed buildings.
    place_fn must return (x, y, rotated). Returns (x, y, rotated) or None.
    """
    for _ in range(max_attempts):
        x, y, rotated = place_fn()
        w, h = _dims(name, rotated)
        # Check overlap against all placed buildings
        overlap = False
        for pname, pval in placed.items():
            if pname in _FP:
                px, py = _pos_xy(pval)
                pw, ph = _dims(pname, _pos_rot(pval))
                if _rects_overlap(x, y, w, h, px, py, pw, ph, gap=_OVERLAP_GAP):
                    overlap = True
                    break
        if not overlap:
            return x, y, rotated
    return None


def generate_layouts(site_width, site_length, wind_dir,
                     n_results=10, min_rules_passing=10, max_pool=5000,
                     gate_side="N", gate_ratio=0.5, gis_corner="NE"):
    """
    Constrained random placement engine for all groups (Phase 05).
    Infrastructure-first: road network is fixed, then buildings are placed hierarchically.
    Each building is placed sequentially with collision checks against all prior buildings.

    Args:
        gate_side       : "N" | "S" | "E" | "W" — which boundary edge the site gate is on.
        gate_ratio      : 0.0–1.0 position along that edge (0.5 = center).
        gis_corner      : "NE" | "NW" | "SE" | "SW" — which corner anchors GIS.

    Returns up to n_results layout dicts, sorted by total_penalty (lowest first).
    Each dict: {positions, rack_endpoints, groups, racks, scoring, road, gate_point}
    """
    sw, sl = site_width, site_length
    gate_point = compute_gate_point(gate_side, gate_ratio, sw, sl)

    candidates = []

    for _ in range(max_pool):
        placed = {}

        # 1. Gate House (FIXED — adjacent to site gate) — always succeeds
        gh_x, gh_y, _ = _place_gate_house(sw, sl, gate_side=gate_side, gate_ratio=gate_ratio)
        placed["Gate House"] = (gh_x, gh_y, False)

        # 2. GIS (FIXED — user-chosen corner) — always succeeds
        gis_x, gis_y, _ = _place_gis(sw, sl, corner=gis_corner)
        placed["GIS"] = (gis_x, gis_y, False)

        # 3. Power Block (center, minimal jitter) — collision-aware
        result = _try_place_collision_aware(sw, sl, "Power Block", placed,
                    lambda: _place_power_block(sw, sl), max_attempts=50)
        if result is None: continue
        placed["Power Block"] = result

        # 4. Admin Building (near GH + PB) — collision-aware
        pb_x, pb_y = placed["Power Block"][:2]
        result = _try_place_collision_aware(sw, sl, "Admin Building", placed,
                    lambda: _place_admin(sw, sl, gh_x, gh_y, pb_x, pb_y), max_attempts=50)
        if result is None: continue
        placed["Admin Building"] = result

        # 5. Cooling Tower (leeward edge) — collision-aware
        result = _try_place_collision_aware(sw, sl, "Cooling Tower", placed,
                    lambda: _place_cooling_tower(sw, sl, wind_dir), max_attempts=100)
        if result is None: continue
        placed["Cooling Tower"] = result

        # 6. WT/WWT (leeward, setback) — collision-aware
        result = _try_place_collision_aware(sw, sl, "WT/WWT", placed,
                    lambda: _place_wt_wwt(sw, sl, wind_dir), max_attempts=100)
        if result is None: continue
        placed["WT/WWT"] = result

        # 7. Water (near WT/WWT) — collision-aware
        ww_x, ww_y, ww_rotated = placed["WT/WWT"]
        result = _try_place_collision_aware(sw, sl, "Water", placed,
                    lambda: _place_water(sw, sl, ww_x, ww_y, ww_rotated), max_attempts=100)
        if result is None: continue
        placed["Water"] = result

        # 8. Flare (leeward corner) — collision-aware
        result = _try_place_collision_aware(sw, sl, "Flare", placed,
                    lambda: _place_flare(sw, sl, wind_dir), max_attempts=100)
        if result is None: continue
        placed["Flare"] = result

        # 9. LPG/Metering (corner, setback) — collision-aware
        result = _try_place_collision_aware(sw, sl, "LPG/Metering", placed,
                    lambda: _place_lpg(sw, sl), max_attempts=100)
        if result is None: continue
        placed["LPG/Metering"] = result

        # 10. Warehouse (available space) — collision-aware
        wh_x, wh_y, wh_rotated = _place_warehouse(sw, sl, placed)
        placed["Warehouse"] = (wh_x, wh_y, wh_rotated)

        positions = dict(placed)

        # Final overlap sanity check
        if _has_any_overlap(positions):
            continue

        groups = get_all_groups(site_width, site_length, positions=positions)

        # Build the perimeter road by A* on a 2.5m occupancy grid that
        # includes every placed building. Returns None if the road cannot
        # route through the setback ring — reject the candidate in that case.
        road = build_road_network(sw, sl, groups)
        if road is None:
            continue

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
                "road":           road,
                "gate_point":     gate_point,
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

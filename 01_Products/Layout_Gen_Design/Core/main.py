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

_OVERLAP_GAP = 6  # Enforce 6m gap so adjacent 3m building buffers can touch but not overlap


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
    names = []
    for name, val in positions.items():
        if name in _FP:
            x, y = _pos_xy(val)
            w, h = _dims(name, _pos_rot(val))
            items.append((x, y, w, h))
            names.append(name)
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            n1, n2 = names[i], names[j]
            # Exception: Water vs WT/WWT can have 3m gap instead of _OVERLAP_GAP
            if (n1 == "Water" and n2 == "WT/WWT") or (n1 == "WT/WWT" and n2 == "Water"):
                current_gap = 3
            else:
                current_gap = _OVERLAP_GAP
            if _rects_overlap(*items[i], *items[j], gap=current_gap):
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



def _place_gate_house(sw, sl, gate_side="N", gate_ratio=0.5, gh_position="right",
                       anchor_offset=0):
    """Gate House: placed to the right or left of the site gate, inside the plot.

    The gate is the physical entry point on the plot boundary. Gate House
    sits inside the plot next to the gate.

    Args:
        sw, sl:         site width and length in metres.
        gate_side:      "N" | "S" | "E" | "W" — which boundary edge the gate is on.
        gate_ratio:     0.0–1.0 position along that edge (0.5 = center).
        gh_position:    "right" | "left" — which side of the gate the GH sits on
                        (when looking from outside into the plot).
        anchor_offset:  inward distance from the gate-side boundary in metres.
                        0 keeps GH flush with the boundary (legacy behaviour).
    """
    w, h = _FP["Gate House"]
    gate_x, gate_y = compute_gate_point(gate_side, gate_ratio, sw, sl)
    gap = 10  # gap of 10m between gate opening and Gate House

    if gate_side == "N":
        y = sl - h - anchor_offset
        if gh_position == "right":
            x = gate_x + gap
        else:
            x = gate_x - w - gap
    elif gate_side == "S":
        y = anchor_offset
        if gh_position == "right":
            x = gate_x + gap
        else:
            x = gate_x - w - gap
    elif gate_side == "E":
        x = sw - w - anchor_offset
        if gh_position == "right":
            y = gate_y - h - gap
        else:
            y = gate_y + gap
    elif gate_side == "W":
        x = anchor_offset
        if gh_position == "right":
            y = gate_y + gap
        else:
            y = gate_y - h - gap
    else:
        raise ValueError(f"gate_side must be N/S/E/W, got {gate_side!r}")

    x = _clamp(x, 0, sw - w)
    y = _clamp(y, 0, sl - h)
    return x, y, False


def _place_gis(sw, sl, corner="NE", anchor_offset=0):
    """GIS: FIXED at chosen corner. Rotation fixed.

    Args:
        corner:         "NE" | "NW" | "SE" | "SW". Default "NE".
        anchor_offset:  inward distance from both corner edges in metres.
                        0 keeps GIS flush with the corner (legacy behaviour).
    """
    w, h = _FP["GIS"]
    gis_margin = anchor_offset
    if corner == "NE":
        x, y = sw - w - gis_margin, sl - h - gis_margin
    elif corner == "NW":
        x, y = gis_margin,           sl - h - gis_margin
    elif corner == "SE":
        x, y = sw - w - gis_margin, gis_margin
    elif corner == "SW":
        x, y = gis_margin,           gis_margin
    else:
        raise ValueError(f"gis_corner must be NE/NW/SE/SW, got {corner!r}")
    return x, y, False


def _place_power_block(sw, sl, margin):
    """Power Block: near center with ±5% random variation (tight site).
    Square footprint, so rotation is a no-op."""
    w, h = _FP["Power Block"]
    cx = (sw - w) / 2 + random.uniform(-sw * 0.05, sw * 0.05)
    cy = (sl - h) / 2 + random.uniform(-sl * 0.05, sl * 0.05)
    return _clamp(cx, margin, sw - w - margin), _clamp(cy, margin, sl - h - margin), False


def _place_admin(sw, sl, gh_x, gh_y, pb_x, pb_y, margin):
    """Admin: near Gate House AND Power Block (north zone, center-ish)."""
    rotated = _maybe_rotate("Admin Building")
    w, h = _dims("Admin Building", rotated)
    pb_w, pb_h = _FP["Power Block"]   # square
    gh_w, gh_h = _FP["Gate House"]    # square
    gh_cx, gh_cy = gh_x + gh_w / 2, gh_y + gh_h / 2
    pb_cx, pb_cy = pb_x + pb_w / 2, pb_y + pb_h / 2

    for _ in range(500):
        # Search near the north zone, between GH and PB
        x = random.uniform(margin, sw - w - margin)
        y = random.uniform(pb_y + pb_h + 5, sl - h - margin)
        cx, cy = x + w / 2, y + h / 2
        d_gh = math.dist((cx, cy), (gh_cx, gh_cy))
        d_pb = math.dist((cx, cy), (pb_cx, pb_cy))
        if d_gh <= 80 and d_pb <= 120:
            return x, y, rotated
    # Fallback: just above Power Block
    return (_clamp(pb_x + pb_w / 2 - w / 2, margin, sw - w - margin),
            _clamp(pb_y + pb_h + 10, margin, sl - h - margin),
            rotated)


def _place_cooling_tower(sw, sl, wind_dir, margin):
    """Cooling Tower: constrained to leeward (downwind) zone.
    Native footprint is 40w x 183h — very tall and narrow. May rotate 90°.
    """
    rotated = _maybe_rotate("Cooling Tower")
    w, h = _dims("Cooling Tower", rotated)
    depth = random.uniform(margin, margin + 15)

    # Leeward = opposite of wind direction
    if wind_dir == "East":
        x = depth   # left side (downwind)
        y = random.uniform(margin, max(margin, sl - h - margin))
    elif wind_dir == "West":
        x = sw - w - depth  # right side (downwind)
        y = random.uniform(margin, max(margin, sl - h - margin))
    elif wind_dir == "North":
        x = random.uniform(margin, max(margin, sw - w - margin))
        y = depth  # bottom side (downwind)
    else:  # South
        x = random.uniform(margin, max(margin, sw - w - margin))
        y = sl - h - depth  # top side (downwind)

    return (_clamp(x, margin, sw - w - margin),
            _clamp(y, margin, max(margin, sl - h - margin)),
            rotated)


def _place_wt_wwt(sw, sl, wind_dir, margin):
    """WT/WWT: setback ≥ 15 m, prefer downwind side. May rotate 90°."""
    rotated = _maybe_rotate("WT/WWT")
    w, h = _dims("WT/WWT", rotated)
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

    return (_clamp(x, margin, sw - w - margin),
            _clamp(y, margin, sl - h - margin),
            rotated)


def _place_water(sw, sl, ww_x, ww_y, ww_rotated, margin):
    """Water: near WT/WWT, adjacent but non-overlapping. Water is square (no rotation)."""
    w, h = _FP["Water"]   # square
    ww_w, ww_h = _dims("WT/WWT", ww_rotated)
    # Try placing adjacent to WT/WWT (right, left, top, bottom)
    candidates = [
        (ww_x + ww_w + 3, ww_y),              # right of WT/WWT
        (ww_x - w - 3, ww_y),                  # left of WT/WWT
        (ww_x, ww_y + ww_h + 3),               # above WT/WWT
        (ww_x, ww_y - h - 3),                  # below WT/WWT
        (ww_x + ww_w + 3, ww_y + ww_h - h),    # right-top aligned
    ]
    for cx, cy in candidates:
        cx = _clamp(cx, margin, sw - w - margin)
        cy = _clamp(cy, margin, sl - h - margin)
        # Verify non-overlap with WT/WWT
        if not _rects_overlap(cx, cy, w, h, ww_x, ww_y, ww_w, ww_h, gap=3):
            return cx, cy, False
    # Fallback with randomness
    for _ in range(200):
        x = ww_x + random.uniform(-80, 80)
        y = ww_y + random.uniform(-80, 80)
        x = _clamp(x, margin, sw - w - margin)
        y = _clamp(y, margin, sl - h - margin)
        if not _rects_overlap(x, y, w, h, ww_x, ww_y, ww_w, ww_h, gap=3):
            return x, y, False
    # Last resort
    return (_clamp(ww_x + ww_w + 8, margin, sw - w - margin),
            _clamp(ww_y, margin, sl - h - margin),
            False)


def _place_flare(sw, sl, wind_dir, margin):
    """Flare: on leeward edge, preferably in a corner. 40x40 square (no rotation)."""
    w, h = _FP["Flare"]
    depth = random.uniform(margin, margin + 15)

    # Leeward corner placement
    if wind_dir == "East":
        x = depth
        y = random.choice([random.uniform(margin, margin + 30),
                           random.uniform(sl - h - 30, sl - h - margin)])
    elif wind_dir == "West":
        x = sw - w - depth
        y = random.choice([random.uniform(margin, margin + 30),
                           random.uniform(sl - h - 30, sl - h - margin)])
    elif wind_dir == "North":
        y = depth
        x = random.choice([random.uniform(margin, margin + 30),
                           random.uniform(sw - w - 30, sw - w - margin)])
    else:  # South
        y = sl - h - depth
        x = random.choice([random.uniform(margin, margin + 30),
                           random.uniform(sw - w - 30, sw - w - margin)])

    return _clamp(x, margin, sw - w - margin), _clamp(y, margin, sl - h - margin), False


def _place_lpg(sw, sl, margin):
    """LPG/Metering: setback ≥ 15 m, corner placement. May rotate 90°."""
    rotated = _maybe_rotate("LPG/Metering")
    w, h = _dims("LPG/Metering", rotated)
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
    return (_clamp(x, margin, sw - w - margin),
            _clamp(y, margin, sl - h - margin),
            rotated)


def _place_warehouse(sw, sl, placed_positions, margin):
    """Warehouse: find available space, avoid overlaps with placed buildings.
    May rotate 90°."""
    for _ in range(500):
        rotated = _maybe_rotate("Warehouse")
        w, h = _dims("Warehouse", rotated)
        x = random.uniform(margin, sw - w - margin)
        y = random.uniform(margin, sl - h - margin)
        # Check overlap with all already-placed buildings
        overlap = False
        for name, pval in placed_positions.items():
            if name in _FP:
                px, py = _pos_xy(pval)
                pw, ph = _dims(name, _pos_rot(pval))
                if _rects_overlap(x, y, w, h, px, py, pw, ph, gap=_OVERLAP_GAP):
                    overlap = True
                    break
        if not overlap:
            return x, y, rotated
    # Fallback: bottom-left, unrotated
    return margin, margin, False


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
                # Exception: Water vs WT/WWT can have 3m gap instead of _OVERLAP_GAP
                if (name == "Water" and pname == "WT/WWT") or (name == "WT/WWT" and pname == "Water"):
                    current_gap = 3
                else:
                    current_gap = _OVERLAP_GAP
                if _rects_overlap(x, y, w, h, px, py, pw, ph, gap=current_gap):
                    overlap = True
                    break
        if not overlap:
            return x, y, rotated
    return None


def generate_layouts(site_width, site_length, wind_dir,
                     n_results=10, min_rules_passing=10, max_pool=5000,
                     gate_side="N", gate_ratio=0.5, gh_position="right",
                     gis_corner="NE", boundary_margin=15, anchor_offset=0):
    """
    Constrained random placement engine for all groups (Phase 05).
    Infrastructure-first: road network is fixed, then buildings are placed hierarchically.
    Each building is placed sequentially with collision checks against all prior buildings.

    Args:
        gate_side       : "N" | "S" | "E" | "W" — which boundary edge the site gate is on.
        gate_ratio      : 0.0–1.0 position along that edge (0.5 = center).
        gh_position     : "right" | "left" — Gate House side relative to gate.
        gis_corner      : "NE" | "NW" | "SE" | "SW" — which corner anchors GIS.

    Returns up to n_results layout dicts, sorted by total_penalty (lowest first).
    Each dict: {positions, rack_endpoints, groups, racks, scoring, road, gate_point}
    """
    sw, sl = site_width, site_length
    gate_point = compute_gate_point(gate_side, gate_ratio, sw, sl)

    candidates = []

    for _ in range(max_pool):
        placed = {}

        # 1. Gate House (FIXED — to right/left of site gate, inside plot) — always succeeds
        gh_x, gh_y, _ = _place_gate_house(sw, sl, gate_side=gate_side,
                                           gate_ratio=gate_ratio,
                                           gh_position=gh_position,
                                           anchor_offset=anchor_offset)
        placed["Gate House"] = (gh_x, gh_y, False)

        # 2. GIS (FIXED — user-chosen corner) — always succeeds
        gis_x, gis_y, _ = _place_gis(sw, sl, corner=gis_corner, anchor_offset=anchor_offset)
        placed["GIS"] = (gis_x, gis_y, False)

        # 3. Power Block (center, minimal jitter) — collision-aware
        result = _try_place_collision_aware(sw, sl, "Power Block", placed,
                    lambda: _place_power_block(sw, sl, boundary_margin), max_attempts=50)
        if result is None: continue
        placed["Power Block"] = result

        # 4. Admin Building (near GH + PB) — collision-aware
        pb_x, pb_y = placed["Power Block"][:2]
        result = _try_place_collision_aware(sw, sl, "Admin Building", placed,
                    lambda: _place_admin(sw, sl, gh_x, gh_y, pb_x, pb_y, boundary_margin), max_attempts=50)
        if result is None: continue
        placed["Admin Building"] = result

        # 5. Cooling Tower (leeward edge) — collision-aware
        result = _try_place_collision_aware(sw, sl, "Cooling Tower", placed,
                    lambda: _place_cooling_tower(sw, sl, wind_dir, boundary_margin), max_attempts=100)
        if result is None: continue
        placed["Cooling Tower"] = result

        # 6. WT/WWT (leeward, setback) — collision-aware
        result = _try_place_collision_aware(sw, sl, "WT/WWT", placed,
                    lambda: _place_wt_wwt(sw, sl, wind_dir, boundary_margin), max_attempts=100)
        if result is None: continue
        placed["WT/WWT"] = result

        # 7. Water (near WT/WWT) — collision-aware
        ww_x, ww_y, ww_rotated = placed["WT/WWT"]
        result = _try_place_collision_aware(sw, sl, "Water", placed,
                    lambda: _place_water(sw, sl, ww_x, ww_y, ww_rotated, boundary_margin), max_attempts=100)
        if result is None: continue
        placed["Water"] = result

        # 8. Flare (leeward corner) — collision-aware
        result = _try_place_collision_aware(sw, sl, "Flare", placed,
                    lambda: _place_flare(sw, sl, wind_dir, boundary_margin), max_attempts=100)
        if result is None: continue
        placed["Flare"] = result

        # 9. LPG/Metering (corner, setback) — collision-aware
        result = _try_place_collision_aware(sw, sl, "LPG/Metering", placed,
                    lambda: _place_lpg(sw, sl, boundary_margin), max_attempts=100)
        if result is None: continue
        placed["LPG/Metering"] = result

        # 10. Warehouse (available space) — collision-aware
        wh_x, wh_y, wh_rotated = _place_warehouse(sw, sl, placed, boundary_margin)
        placed["Warehouse"] = (wh_x, wh_y, wh_rotated)

        positions = dict(placed)

        # Final overlap sanity check
        if _has_any_overlap(positions):
            continue

        groups = get_all_groups(site_width, site_length, positions=positions)

        # Build the internal road network connecting the gate to all building
        # entrances via A* on a 2.5m grid. Buildings are inflated by 3m on the
        # grid (no corridor erosion needed). Returns None if any entrance is
        # unreachable — reject the candidate in that case.
        road = build_road_network(sw, sl, groups, gate_point)
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
        scoring = evaluate_all_v2(groups, racks, site_width, site_length, wind_dir,
                                  gate_point=gate_point)
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

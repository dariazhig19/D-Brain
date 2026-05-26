"""Phase 06 — Steps 1.1–1.3: Grid-first block placement + fire road sketches.

Steps covered:
  1.1  2m grid setup, all blocks snap to grid
  1.2  Placement sequence + fire road geometry
  1.3  Block buffer: 15m between block edges
"""

import random
import math
import networkx as nx
from Core.Grid import Grid
from Core.Pathfind import astar

# ── Constants ──────────────────────────────────────────────────────────
CELL_SIZE         = 2    # metres per grid cell
ROAD_BUFFER       = 8    # min distance from block edge to ANY road centerline (default, no rack adjacent)
BLOCK_BUFFER      = 16   # min gap between two block edges (default, no rack between)
BOUNDARY_MARGIN   = 17   # min distance from floated block to site boundary (perimeter CL at 9m + 8m road buffer)
BOUNDARY_TOLERANCE = 10  # magnet placer allows floated blocks to spill up to 10m outside the plot
PB_RING_OFFSET    = 9    # ring CL from PB face — 8m road buffer + 1 cell past the buffer line on the 2m grid
PERIMETER_SETBACK = 5    # perimeter road outer edge from plot boundary ← configurable
PERIMETER_ROAD_W  = 8    # perimeter road width
PERIMETER_CL_DIST = PERIMETER_SETBACK + PERIMETER_ROAD_W / 2   # 9m from boundary

# ── Rack constants (Phase 06 — § 1.2-RACK) ─────────────────────────────
# Single rack type, 6m wide, connects 5 process blocks. See !Scoring_Logic.md.
RACK_BLOCKS = frozenset({
    "Power Block", "Cooling Tower", "WT/WWT",
    "RAW Water Tank", "Demi Water Tank",
})
RACK_WIDTH = 6   # metres
# Per-side buffer offsets for "need rack" blocks. Two regimes per side:
#   - "no rack" on this side:    road CL at 8m, block-to-block 16m  (baseline)
#   - "with rack" on this side:  road CL at 14m, block-to-block 28m (rack takes space)
# Plus two rack-centerline offsets for the two layouts:
#   - Case 1 (block → rack → road):  rack CL at 6m
#   - Case 2 (block → road → rack):  rack CL at 22m
ROAD_W_RACK_OFFSET   = 14   # road CL on a side that has a rack
B2B_W_RACK_OFFSET    = 28   # block-to-block on a side that has a rack
RACK_CASE1_OFFSET    = 6
RACK_CASE2_OFFSET    = 22

# ── Block catalog ──────────────────────────────────────────────────────────
# Source of truth: Notes/!Scoring_Logic.md — 10 confirmed blocks
# (width, height in metres) — non-square blocks may be rotated 90°
BLOCK_FOOTPRINTS = {
    "Power Block":    (150, 150),
    "Cooling Tower":  (40,  183),
    "Admin Building": (30,   25),
    "Gate House":     (12,   12),
    "GIS":            (110,  51),
    "Flare":          (40,   40),
    "WT/WWT":         (81,   56),
    "Warehouse":      (59,   40),
    "RAW Water Tank": (37,   37),
    "Demi Water Tank":(25,   12),
}

BLOCK_COLORS = {
    "Power Block":    "#4a90d9",
    "Cooling Tower":  "#7ed6a0",
    "Admin Building": "#f5a623",
    "Gate House":     "#9b59b6",
    "GIS":            "#2c3e50",
    "Flare":          "#e74c3c",
    "WT/WWT":         "#34495e",
    "Warehouse":      "#e67e22",
    "RAW Water Tank": "#00bcd4",
    "Demi Water Tank":"#1abc9c",
}

# ── Grid helpers ───────────────────────────────────────────────────────────
def snap(v):
    return round(v / CELL_SIZE) * CELL_SIZE

def snap_xy(x, y):
    return snap(x), snap(y)

# ── Overlap check ──────────────────────────────────────────────────────────
def _overlaps(ax, ay, aw, ah, bx, by, bw, bh, gap=BLOCK_BUFFER):
    return not (ax + aw + gap <= bx or bx + bw + gap <= ax or
                ay + ah + gap <= by or by + bh + gap <= ay)


def pair_min_gap(name_a, name_b):
    """Minimum allowed edge-to-edge distance between two real blocks.

    Keyed on rack membership (`RACK_BLOCKS`):
      rack ↔ rack       → ROAD_W_RACK_OFFSET (14m, shared rack-side road CL)
      no-rack ↔ no-rack → ROAD_BUFFER       (8m, shared no-rack road CL)
      mixed             → B2B_W_RACK_OFFSET (28m, rack-side b2b)

    Virtual `_…_zone` entries are handled by the caller (gap=0)."""
    a_rack = name_a in RACK_BLOCKS
    b_rack = name_b in RACK_BLOCKS
    if a_rack and b_rack:
        return ROAD_W_RACK_OFFSET * 2   # 28m (14m + 14m)
    if not a_rack and not b_rack:
        return ROAD_BUFFER * 2          # 16m (8m + 8m)
    return B2B_W_RACK_OFFSET            # 28m (mixed)


def _overlaps_any(name, placed, x, y, w, h):
    """Per-pair edge-to-edge gap, keyed on rack membership via `pair_min_gap`.

    Virtual zones (names with `_` prefix — `_pb_ring_zone`, `_gate_spur_zone`,
    `_ring_spur_zone`) use gap=0 because their rectangle already includes the
    8m road buffer; a block touching the zone edge is already 8m from the
    road centerline."""
    for bname, (bx, by, bw, bh) in placed.items():
        if bname == "_gate_death_zone" and name not in ("Cooling Tower", "WT/WWT", "Warehouse", "Flare", "Admin", "Demi Water"):
            continue
        current_gap = 0 if bname.startswith("_") else pair_min_gap(name, bname)
        if _overlaps(x, y, w, h, bx, by, bw, bh, current_gap):
            return True
    return False


def _within_relaxed_bounds(x, y, w, h, sw, sl, tol=BOUNDARY_TOLERANCE):
    """Allow placement up to `tol` metres outside the plot on any side."""
    return (x >= -tol and y >= -tol
            and x + w <= sw + tol and y + h <= sl + tol)

# ── Placement helpers ──────────────────────────────────────────────────────
def place_anchor(sw, sl, name, edge, ratio, offset):
    """Fixed anchor — grid-snapped. Returns (x, y, w, h)."""
    w, h = BLOCK_FOOTPRINTS[name]
    if   edge == "N": x, y = (sw - w) * ratio, sl - h - offset
    elif edge == "S": x, y = (sw - w) * ratio, offset
    elif edge == "E": x, y = sw - w - offset,  (sl - h) * ratio
    elif edge == "W": x, y = offset,            (sl - h) * ratio
    else: raise ValueError(f"edge must be N/S/E/W, got {edge!r}")
    x, y = snap_xy(x, y)
    return max(0, min(x, sw - w)), max(0, min(y, sl - h)), w, h


def _try_place(sw, sl, name, placed, sample_fn, max_attempts=500, prefer_near=None):
    """
    Try to place block using sample_fn() → (x, y).
    Tries BOTH orientations (w×h and h×w) at each sampled point.
    Uses name-aware gap exceptions (RAW Water Tank neighbors get 3m gap).
    prefer_near: optional (cx, cy) — selects from top 10% closest (matches Main.py).
    Returns (x, y, w, h) or None.
    """
    base_w, base_h = BLOCK_FOOTPRINTS[name]
    orientations = [(base_w, base_h)]
    if base_w != base_h:
        orientations.append((base_h, base_w))

    valid = []
    for _ in range(max_attempts):
        rx, ry = sample_fn()
        for w, h in orientations:
            x, y = snap_xy(rx, ry)
            # Enforce BOUNDARY_MARGIN from all site edges (anchors use place_anchor, not _try_place)
            m = BOUNDARY_MARGIN
            x = max(m, min(x, sw - w - m))
            y = max(m, min(y, sl - h - m))
            if not _overlaps_any(name, placed, x, y, w, h):
                valid.append((x, y, w, h))
        if len(valid) >= 20:
            break

    if not valid:
        return None
    if prefer_near:
        cx, cy = prefer_near
        valid.sort(key=lambda v: (v[0]+v[2]/2 - cx)**2 + (v[1]+v[3]/2 - cy)**2)
        # Top 10% closest — matches Main.py top_n = len // 10 logic
        return random.choice(valid[:max(1, len(valid) // 10)])
    return random.choice(valid)


# ── Magnet placer (Phase 06, Step 1.1+) ────────────────────────────────────
def _slide(t_start, t_extent, b_extent, inset, i, n):
    """i-th of n evenly spaced lateral positions for a block of extent
    `b_extent` sliding along a target's side of extent `t_extent`. `inset`
    forces a minimum corner overlap so candidates are not perfectly flush
    with the target's corner (avoids 0-overlap degenerate adjacency)."""
    lo = t_start - b_extent + inset
    hi = t_start + t_extent - inset
    if n <= 1:
        return (lo + hi) / 2
    return lo + (hi - lo) * i / (n - 1)


def _magnet_candidates(name, w, h, placed, sw, sl,
                       samples_per_side=7, lateral_inset=4, target=None):
    """Generate (x, y) candidates by snapping a block (w×h, named `name`) at
    the pair-appropriate magnet distance against each side of every real
    placed block. Honors relaxed bounds (`_within_relaxed_bounds`) and the
    per-pair collision check (`_overlaps_any`)."""
    cands = []
    for tname, (tx, ty, tw, th) in placed.items():
        if tname.startswith("_"):
            continue
        if target is not None and tname != target:
            continue
        # Do not use fixed anchors as default magnets unless explicitly targeted
        if target is None and tname in ("Gate House", "GIS", "RAW Water Tank"):
            continue
        D = pair_min_gap(name, tname)
        sides = []
        # North of T
        sides += [(_slide(tx, tw, w, lateral_inset, i, samples_per_side),
                   ty + th + D) for i in range(samples_per_side)]
        # South of T
        sides += [(_slide(tx, tw, w, lateral_inset, i, samples_per_side),
                   ty - h - D) for i in range(samples_per_side)]
        # East of T
        sides += [(tx + tw + D,
                   _slide(ty, th, h, lateral_inset, i, samples_per_side))
                  for i in range(samples_per_side)]
        # West of T
        sides += [(tx - w - D,
                   _slide(ty, th, h, lateral_inset, i, samples_per_side))
                  for i in range(samples_per_side)]
        for x, y in sides:
            x, y = snap_xy(x, y)
            if not _within_relaxed_bounds(x, y, w, h, sw, sl):
                continue
            if _overlaps_any(name, placed, x, y, w, h):
                continue
            cands.append((x, y))
    return cands


def _try_magnet_place(sw, sl, name, placed, prefer_near=None, filter_fn=None, magnet_target=None):
    """Place a floated block by magnetizing to a previously placed block.

    Tries both orientations. Returns (x, y, w, h) or None when no candidate
    survives bounds + collision checks. `prefer_near` keeps the existing
    top-10%-closest selection so blocks still cluster near PB. `filter_fn`
    can be used to restrict placement to specific zones (e.g. Leeward)."""
    base_w, base_h = BLOCK_FOOTPRINTS[name]
    orientations = [(base_w, base_h)]
    if base_w != base_h:
        orientations.append((base_h, base_w))

    valid = []
    for w, h in orientations:
        for x, y in _magnet_candidates(name, w, h, placed, sw, sl, target=magnet_target):
            if filter_fn is None or filter_fn(x, y, w, h):
                valid.append((x, y, w, h))

    # Fallback to any valid magnet target if the specified target fails
    if magnet_target is not None and not valid:
        for w, h in orientations:
            for x, y in _magnet_candidates(name, w, h, placed, sw, sl, target=None):
                if filter_fn is None or filter_fn(x, y, w, h):
                    valid.append((x, y, w, h))

    if not valid:
        return None
    if prefer_near is not None:
        cx, cy = prefer_near
        valid.sort(key=lambda v: (v[0] + v[2] / 2 - cx) ** 2
                                + (v[1] + v[3] / 2 - cy) ** 2)
        valid = valid[:max(1, len(valid) // 10)]
    return random.choice(valid)


# ── Fire road geometry ─────────────────────────────────────────────────────
def build_pb_ring_road(pb_x, pb_y, pb_w, pb_h, offset=PB_RING_OFFSET):
    """Closed polyline of PB ring road centerline."""
    x1, y1 = pb_x - offset, pb_y - offset
    x2, y2 = pb_x + pb_w + offset, pb_y + pb_h + offset
    return [(x1,y1),(x2,y1),(x2,y2),(x1,y2),(x1,y1)]

def build_perimeter_road(sw, sl, cl_dist=PERIMETER_CL_DIST):
    """Closed polyline of perimeter fire road centerline."""
    d = cl_dist
    return [(d,d),(sw-d,d),(sw-d,sl-d),(d,sl-d),(d,d)]


# ── Rack — Step A: buffer rectangles per "need rack" block ───────────────
def rack_buffer_rect(block, offset):
    """Axis-aligned rectangle around a block's footprint, inflated by `offset`.

    The rectangle's OUTLINE is a candidate buffer line at distance `offset`
    from the block edge. Returned as `(x, y, w, h)`."""
    bx, by, bw, bh = block["x"], block["y"], block["width"], block["height"]
    return (bx - offset, by - offset, bw + 2 * offset, bh + 2 * offset)


# Six offsets per "need rack" block side, in order of distance from block edge:
#   road_no_rack   8 m   road CL on a side without a rack    (default)
#   b2b_no_rack   16 m   block-to-block on a side without rack (default)
#   case1_rack     6 m   rack CL in Case 1 (rack between block and road)
#   road_w_rack   14 m   road CL on a side that has a rack
#   case2_rack    22 m   rack CL in Case 2 (road between block and rack)
#   b2b_w_rack    28 m   block-to-block on a side that has a rack
RACK_BLOCK_OFFSETS = {
    "road_no_rack": ROAD_BUFFER,            # 8
    "b2b_no_rack":  BLOCK_BUFFER,           # 16
    "case1_rack":   RACK_CASE1_OFFSET,      # 6
    "road_w_rack":  ROAD_W_RACK_OFFSET,     # 14
    "case2_rack":   RACK_CASE2_OFFSET,      # 22
    "b2b_w_rack":   B2B_W_RACK_OFFSET,      # 28
}


def compute_rack_buffers(blocks):
    """Step A — per-block buffer rectangles for the 6 offsets a rack block uses.

    Returns {block_name: {offset_key: rect}} for every block in `RACK_BLOCKS`.
    Each rect's outline is the buffer line at that offset. Blocks not in
    `RACK_BLOCKS` get no entry — they use only the baseline road/b2b buffers."""
    return {
        b["name"]: {
            key: rack_buffer_rect(b, off)
            for key, off in RACK_BLOCK_OFFSETS.items()
        }
        for b in blocks
        if b["name"] in RACK_BLOCKS
    }


def build_rack_spines(rack_buffers, blocks, sw, sl):
    """Phase 06 Steps B-1 to B-4 — build PB-CT spine and candidates.

    Returns:
        spine_centerlines: List of lines (each a list of 2 points).
        candidate_points: List of (x, y) points from RAW and Demi.
        active_cases: Dict of which case was randomly selected for each block.
    """
    active_cases = {}
    for name in ("Power Block", "Cooling Tower", "RAW Water Tank", "Demi Water Tank", "WT/WWT"):
        if name in rack_buffers:
            if name in ("RAW Water Tank", "Demi Water Tank", "WT/WWT"):
                active_cases[name] = "case1_rack"
            else:
                active_cases[name] = random.choice(["case1_rack", "case2_rack"])

    if "Power Block" not in rack_buffers or "Cooling Tower" not in rack_buffers:
        return [], [], active_cases

    pb_rect = rack_buffers["Power Block"][active_cases["Power Block"]]
    ct_rect = rack_buffers["Cooling Tower"][active_cases["Cooling Tower"]]

    raw_cx, raw_cy = 0, 0
    pb_cx, pb_cy = 0, 0
    for b in blocks:
        if b["name"] == "RAW Water Tank":
            raw_cx, raw_cy = b["x"] + b["width"]/2, b["y"] + b["height"]/2
        elif b["name"] == "Power Block":
            pb_cx, pb_cy = b["x"] + b["width"]/2, b["y"] + b["height"]/2

    def get_spine_side(rect, block_cx, block_cy):
        x, y, w, h = rect
        dx = raw_cx - block_cx
        dy = raw_cy - block_cy
        
        if abs(dx) > abs(dy):
            side1 = [(x, y), (x+w, y)]           # Bottom
            side2 = [(x, y+h), (x+w, y+h)]       # Top
        else:
            side1 = [(x, y), (x, y+h)]           # Left
            side2 = [(x+w, y), (x+w, y+h)]       # Right
            
        mid1 = ((side1[0][0]+side1[1][0])/2, (side1[0][1]+side1[1][1])/2)
        mid2 = ((side2[0][0]+side2[1][0])/2, (side2[0][1]+side2[1][1])/2)
        dist1 = (mid1[0]-raw_cx)**2 + (mid1[1]-raw_cy)**2
        dist2 = (mid2[0]-raw_cx)**2 + (mid2[1]-raw_cy)**2
        
        return side1 if dist1 < dist2 else side2

    best_pb_side = get_spine_side(pb_rect, pb_cx, pb_cy)
    
    # We need CT center
    ct_cx, ct_cy = 0, 0
    for b in blocks:
        if b["name"] == "Cooling Tower":
            ct_cx, ct_cy = b["x"] + b["width"]/2, b["y"] + b["height"]/2
            
    best_ct_side = get_spine_side(ct_rect, ct_cx, ct_cy)

    spine_centerlines = [best_pb_side, best_ct_side]

    def side_mid(side):
        return ((side[0][0]+side[1][0])/2, (side[0][1]+side[1][1])/2)
        
    pb_spine_mid = side_mid(best_pb_side)
    candidate_points = []
    
    def get_corners(rect):
        x, y, w, h = rect
        return [(x, y), (x+w, y), (x+w, y+h), (x, y+h)]

    def is_inside(c):
        return 0 <= c[0] <= sw and 0 <= c[1] <= sl

    raw_candidates = []
    rect = rack_buffers.get("RAW Water Tank", {}).get(active_cases.get("RAW Water Tank"))
    if rect:
        corners = get_corners(rect)
        corners = [c for c in corners if is_inside(c)]
        corners.sort(key=lambda c: (c[0]-pb_spine_mid[0])**2 + (c[1]-pb_spine_mid[1])**2)
        raw_candidates = corners[:2]
        candidate_points.extend(raw_candidates)

    demi_candidates = []
    rect = rack_buffers.get("Demi Water Tank", {}).get(active_cases.get("Demi Water Tank"))
    if rect:
        corners = get_corners(rect)
        corners = [c for c in corners if is_inside(c)]
        corners.sort(key=lambda c: (c[0]-pb_spine_mid[0])**2 + (c[1]-pb_spine_mid[1])**2)
        demi_candidates = corners[:2]
        candidate_points.extend(demi_candidates)

    wwt_pt = None
    kept_raw = None
    kept_demi = None
    wwt_rect = rack_buffers.get("WT/WWT", {}).get(active_cases.get("WT/WWT"))
    
    if wwt_rect and candidate_points:
        wwt_x, wwt_y, wwt_w, wwt_h = wwt_rect
        wwt_sides = [
            [(wwt_x, wwt_y), (wwt_x+wwt_w, wwt_y)],
            [(wwt_x+wwt_w, wwt_y), (wwt_x+wwt_w, wwt_y+wwt_h)],
            [(wwt_x, wwt_y+wwt_h), (wwt_x+wwt_w, wwt_y+wwt_h)],
            [(wwt_x, wwt_y), (wwt_x, wwt_y+wwt_h)]
        ]
        
        def pt_to_segment(p, s1, s2):
            x, y = p
            x1, y1 = s1
            x2, y2 = s2
            px = x2 - x1
            py = y2 - y1
            norm = px*px + py*py
            u = ((x - x1) * px + (y - y1) * py) / float(norm) if norm else 0
            if 0 <= u <= 1:
                proj = (x1 + u * px, y1 + u * py)
                return True, proj, math.hypot(x - proj[0], y - proj[1])
            d1 = math.hypot(x - x1, y - y1)
            d2 = math.hypot(x - x2, y - y2)
            if d1 < d2:
                return False, s1, d1
            return False, s2, d2

        best_proj_dist = float('inf')
        best_proj_pair = None
        
        for pt in candidate_points:
            closest_dist = float('inf')
            closest_proj = None
            closest_is_perp = False
            for s1, s2 in wwt_sides:
                is_perp, proj, d = pt_to_segment(pt, s1, s2)
                if d < closest_dist:
                    closest_dist = d
                    closest_proj = proj
                    closest_is_perp = is_perp
            if closest_is_perp and closest_dist < best_proj_dist:
                best_proj_dist = closest_dist
                best_proj_pair = (pt, closest_proj)
                
        if best_proj_pair:
            kept_source = best_proj_pair[0]
            wwt_pt = best_proj_pair[1]
        else:
            wwt_corners = get_corners(wwt_rect)
            wwt_pt = min(wwt_corners, key=lambda c: (c[0]-raw_cx)**2 + (c[1]-raw_cy)**2)
            kept_source = min(candidate_points, key=lambda c: (c[0]-wwt_pt[0])**2 + (c[1]-wwt_pt[1])**2)
            
        def dist(p1, p2):
            return math.hypot(p1[0]-p2[0], p1[1]-p2[1])

        if kept_source in raw_candidates:
            kept_raw = kept_source
            if demi_candidates:
                kept_demi = min(demi_candidates, key=lambda c: dist(c, kept_raw))
        else:
            kept_demi = kept_source
            if raw_candidates:
                kept_raw = min(raw_candidates, key=lambda c: dist(c, kept_demi))

    water_triangle = []
    if kept_raw: water_triangle.append(kept_raw)
    if kept_demi: water_triangle.append(kept_demi)
    if wwt_pt: water_triangle.append(wwt_pt)

    return spine_centerlines, candidate_points, active_cases, water_triangle


def build_gate_spur(site_w, site_l, gate_pt):
    """Primary-road polyline from the gate (on the boundary) to the perimeter
    road centerline. Always axis-aligned.
    """
    gx, gy = gate_pt
    px_min, px_max = 9, site_w - 9
    py_min, py_max = 9, site_l - 9

    if gy > py_max: return [gate_pt, (gx, py_max)]
    if gy < py_min: return [gate_pt, (gx, py_min)]
    if gx > px_max: return [gate_pt, (px_max, gy)]
    if gx < px_min: return [gate_pt, (px_min, gy)]
    # Gate inside perimeter rect (shouldn't happen for a boundary gate)
    return [gate_pt, (gx, py_max)]


_FIXED_BLOCKS = ("Gate House", "GIS", "RAW Water Tank")


def _spur_exclusion_rect(line, buffer=ROAD_BUFFER):
    """Axis-aligned bounding box of a 2-point spur line inflated by `buffer`
    on all sides. Used as a virtual exclusion zone during floated-block
    placement so blocks stay `buffer` metres away from any spur centerline."""
    if not line or len(line) < 2:
        return None
    xs = [p[0] for p in line]
    ys = [p[1] for p in line]
    x0, x1 = min(xs) - buffer, max(xs) + buffer
    y0, y1 = min(ys) - buffer, max(ys) + buffer
    return (x0, y0, x1 - x0, y1 - y0)


def _seg_aabb_intersect(p1, p2, rx, ry, rw, rh):
    """Axis-aligned segment vs axis-aligned rectangle overlap test.

    A segment that merely touches the rect's edge (tangent) is NOT counted as
    intersecting — a road centerline is allowed to run on the buffer line."""
    x1, y1 = p1
    x2, y2 = p2
    sxmin, sxmax = min(x1, x2), max(x1, x2)
    symin, symax = min(y1, y2), max(y1, y2)
    if sxmax <= rx or sxmin >= rx + rw:
        return False
    if symax <= ry or symin >= ry + rh:
        return False
    return True

def generate_perimeter_segments(placed, pb_cx, pb_cy):
    """B-1 Algorithm for generating perimeter road segments from block buffers."""
    FIRE_ROAD_BLOCKS = {"WT/WWT", "RAW Water Tank", "Cooling Tower", "Warehouse", "GIS", "Admin Building", "Gate House", "Power Block"}
    blocks = {name: bounds for name, bounds in placed.items() if name in FIRE_ROAD_BLOCKS}
    
    def get_buffer(bounds, offset):
        x, y, w, h = bounds
        return (x - offset, y - offset, w + 2*offset, h + 2*offset)
        
    def get_overlap(r1, r2, tol=0.1):
        x1, y1, w1, h1 = r1
        x2, y2, w2, h2 = r2
        l = max(x1, x2)
        r = min(x1 + w1, x2 + w2)
        t = max(y1, y2)
        b = min(y1 + h1, y2 + h2)
        if r >= l - tol and b >= t - tol:
            return (l, t, r - l, b - t)
        return None

    def get_centerline(overlap):
        ox, oy, ow, oh = overlap
        if ow > oh:
            mid_y = oy + oh / 2
            return ((ox, mid_y), (ox + ow, mid_y))
        else:
            mid_x = ox + ow / 2
            return ((mid_x, oy), (mid_x, oy + oh))

    def get_block_buffer_dist(name):
        return 14 if name in RACK_BLOCKS else 8

    segments = []
    connected = set()
    
    def process_pass(buffer_expansion, blocks_to_process):
        block_intersections = {name: [] for name in blocks_to_process}
        for name1, bounds1 in blocks.items():
            if name1 not in blocks_to_process: continue
            for name2, bounds2 in blocks.items():
                if name1 == name2: continue
                b1 = get_block_buffer_dist(name1) + buffer_expansion
                b2 = get_block_buffer_dist(name2) + buffer_expansion
                r1 = get_buffer(bounds1, b1)
                r2 = get_buffer(bounds2, b2)
                overlap = get_overlap(r1, r2)
                if overlap:
                    ox, oy, ow, oh = overlap
                    length = max(ow, oh)
                    seg = get_centerline(overlap)
                    block_intersections[name1].append((length, seg, name2))
                    
        for name, inters in block_intersections.items():
            if inters:
                for length, seg, target_name in inters:
                    if seg not in segments and (seg[1], seg[0]) not in segments:
                        segments.append(seg)
                    connected.add(name)
                    connected.add(target_name)

    # Pass 1: Direct intersections (exact buffer)
    process_pass(0, list(blocks.keys()))
                
    # Pass 2: Tolerance pass (+6m buffer) for unconnected blocks
    unconnected_before_pass2 = [n for n in blocks.keys() if n not in connected]
    process_pass(6, unconnected_before_pass2)
                
    # Pass 3: Orphans
    for name1, bounds1 in blocks.items():
        if name1 in connected: continue
        b1 = get_block_buffer_dist(name1)
        r1 = get_buffer(bounds1, b1)
        x, y, w, h = r1
        edges = [
            ((x, y), (x+w, y)),         # bottom
            ((x, y+h), (x+w, y+h)),     # top
            ((x, y), (x, y+h)),         # left
            ((x+w, y), (x+w, y+h))      # right
        ]
        best_edge = None
        max_dist = -1
        for e in edges:
            mid_x = (e[0][0] + e[1][0]) / 2
            mid_y = (e[0][1] + e[1][1]) / 2
            dist = (mid_x - pb_cx)**2 + (mid_y - pb_cy)**2
            if dist > max_dist:
                max_dist = dist
                best_edge = e
        if best_edge:
            segments.append(best_edge)
            
    return segments

def generate_group_a_access(placed, site_w, site_l, gate_cx, gate_cy):
    """A-2 Algorithm for finding 8m road access lines for Group A blocks."""
    GROUP_A_BLOCKS = {"GIS", "RAW Water Tank", "Cooling Tower", "WT/WWT", "Warehouse", "Admin Building"}
    
    def get_corners_and_lines(bounds):
        x, y, w, h = bounds
        return [
            ("BL", (x, y), [((x, y), (x+w, y)), ((x, y), (x, y+h))]),
            ("BR", (x+w, y), [((x, y), (x+w, y)), ((x+w, y), (x+w, y+h))]),
            ("TL", (x, y+h), [((x, y+h), (x+w, y+h)), ((x, y), (x, y+h))]),
            ("TR", (x+w, y+h), [((x, y+h), (x+w, y+h)), ((x+w, y), (x+w, y+h))])
        ]

    def dist_to_boundary(cx, cy):
        return min(cx, site_w - cx, cy, site_l - cy)
        
    def dist_sq(cx, cy, tx, ty):
        return (cx - tx)**2 + (cy - ty)**2

    segments = []
    
    for name, bounds in placed.items():
        if name not in GROUP_A_BLOCKS:
            continue
            
        offset = 14 if name in RACK_BLOCKS else 8
        bx, by, bw, bh = bounds
        buffer_bounds = (bx - offset, by - offset, bw + 2*offset, bh + 2*offset)
        
        corners = get_corners_and_lines(buffer_bounds)
        
        if name == "Admin Building":
            best_corner = min(corners, key=lambda c: dist_sq(c[1][0], c[1][1], gate_cx, gate_cy))
            segments.extend(best_corner[2])
        elif name == "RAW Water Tank":
            min_dist = min(dist_to_boundary(c[1][0], c[1][1]) for c in corners)
            boundary_corners = [c for c in corners if dist_to_boundary(c[1][0], c[1][1]) <= min_dist + 0.1]
            demi = placed.get("Demi Water Tank")
            if demi:
                demi_cx = demi[0] + demi[2]/2
                demi_cy = demi[1] + demi[3]/2
                best_corner = max(boundary_corners, key=lambda c: dist_sq(c[1][0], c[1][1], demi_cx, demi_cy))
            else:
                best_corner = boundary_corners[0]
            segments.extend(best_corner[2])
        elif name == "WT/WWT":
            best_corner = min(corners, key=lambda c: dist_to_boundary(c[1][0], c[1][1]))
            segments.extend(best_corner[2])
        elif name in ("GIS", "Cooling Tower", "Warehouse"):
            corners_sorted = sorted(corners, key=lambda c: dist_to_boundary(c[1][0], c[1][1]))
            best_corner = corners_sorted[0]
            segments.extend(best_corner[2])
            opp_map = {"BL": "TR", "TR": "BL", "BR": "TL", "TL": "BR"}
            opp_corner = next(c for c in corners if c[0] == opp_map[best_corner[0]])
            segments.extend(opp_corner[2])

    return segments

def build_ring_spur(site_w, site_l, ring_road, blocks, gate_pt):
    """Straight-line primary connector from PB Ring Road to Perimeter Fire Road.

    Picks a perpendicular drop on the side facing the gate; slides the anchor
    laterally if the direct line would overlap a fixed-anchor block (Gate House,
    GIS, RAW Water Tank). May still cross floated blocks — those get
    repositioned in step 2.
    """
    # Inflate fixed blocks by the 8m road buffer so the spur stays >=8m from
    # any fixed block. The intersection test is tangent-friendly, so a spur
    # running exactly on a fixed block's 8m buffer line is allowed.
    BUFFER = 8
    fixed = [(b["x"] - BUFFER, b["y"] - BUFFER,
              b["width"] + 2 * BUFFER, b["height"] + 2 * BUFFER)
             for b in blocks if b["name"] in _FIXED_BLOCKS]

    rxs, rys = zip(*ring_road)
    rxmin, rxmax = min(rxs), max(rxs)
    rymin, rymax = min(rys), max(rys)
    pxmin, pxmax = 9, site_w - 9
    pymin, pymax = 9, site_l - 9

    gx, gy = gate_pt
    dists = [(site_l - gy, "N"), (gy, "S"), (site_w - gx, "E"), (gx, "W")]
    side = min(dists)[1]

    def _clear(p1, p2):
        return not any(_seg_aabb_intersect(p1, p2, *r) for r in fixed)

    SHIFTS = [0, 4, -4, 8, -8, 12, -12, 16, -16, 24, -24, 32, -32,
              40, -40, 50, -50, 60, -60, 80, -80, 100, -100]

    if side in ("N", "S"):
        ring_y = rymax if side == "N" else rymin
        peri_y = pymax if side == "N" else pymin
        x_min = max(rxmin, pxmin)
        x_max = min(rxmax, pxmax)
        target = max(x_min, min(x_max, gx))
        for dx in SHIFTS:
            x = target + dx
            if x < x_min or x > x_max:
                continue
            p1, p2 = (x, ring_y), (x, peri_y)
            if _clear(p1, p2):
                return [p1, p2]
        return [(target, ring_y), (target, peri_y)]

    # E / W
    ring_x = rxmax if side == "E" else rxmin
    peri_x = pxmax if side == "E" else pxmin
    y_min = max(rymin, pymin)
    y_max = min(rymax, pymax)
    target = max(y_min, min(y_max, gy))
    for dy in SHIFTS:
        y = target + dy
        if y < y_min or y > y_max:
            continue
        p1, p2 = (ring_x, y), (peri_x, y)
        if _clear(p1, p2):
            return [p1, p2]
    return [(ring_x, target), (peri_x, target)]

# ── Gate point ─────────────────────────────────────────────────────────────
def compute_gate(sw, sl, side, ratio):
    if side == "N": return (sw * ratio, sl)
    if side == "S": return (sw * ratio, 0)
    if side == "E": return (sw, sl * ratio)
    return (0, sl * ratio)

# ── Stub routing helpers ───────────────────────────────────────────────────
def get_line_points(p1, p2, step=2.0):
    """Sample points along a line segment from p1 to p2 every `step` meters."""
    x1, y1 = p1
    x2, y2 = p2
    dx = x2 - x1
    dy = y2 - y1
    dist = math.sqrt(dx*dx + dy*dy)
    if dist < 0.001:
        return [p1]
    points = []
    n_steps = int(math.ceil(dist / step))
    for s in range(n_steps + 1):
        t = s / n_steps
        points.append((x1 + dx * t, y1 + dy * t))
    return points

def find_nearest_road_point(block_center, road_geometry):
    """Find the point along the road geometry (polyline or list of segments) closest to block_center."""
    cx, cy = block_center
    best_pt = None
    best_dist = math.inf
    
    is_segments = road_geometry and isinstance(road_geometry[0][0], (list, tuple))
    
    if is_segments:
        for p1, p2 in road_geometry:
            pts = get_line_points(p1, p2, step=2.0)
            for rx, ry in pts:
                d = (rx - cx)**2 + (ry - cy)**2
                if d < best_dist:
                    best_dist = d
                    best_pt = (rx, ry)
    else:
        for i in range(len(road_geometry) - 1):
            pts = get_line_points(road_geometry[i], road_geometry[i+1], step=2.0)
            for rx, ry in pts:
                d = (rx - cx)**2 + (ry - cy)**2
                if d < best_dist:
                    best_dist = d
                    best_pt = (rx, ry)
    return best_pt

def closest_buffer_point(b, goal_pt, sw, sl, offset=ROAD_BUFFER):
    """Closest point on the block's road-buffer rectangle OUTLINE to goal_pt.

    A stub starts here so it begins exactly at the side of the block's road
    buffer that faces the goal road — not at a fixed N/S/E/W midpoint. If the
    natural closest point falls outside the site (a fixed anchor flush against
    the boundary), the result is clamped to the nearest in-site point on the
    same buffer edge.
    """
    bx, by, bw, bh = b['x'], b['y'], b['width'], b['height']
    x0, y0 = bx - offset, by - offset
    x1, y1 = bx + bw + offset, by + bh + offset
    gx, gy = goal_pt

    cx = max(x0, min(x1, gx))
    cy = max(y0, min(y1, gy))
    if (cx, cy) == (gx, gy):
        # Goal is inside the buffer rect — snap to nearest edge
        dl, dr, db, dt = gx - x0, x1 - gx, gy - y0, y1 - gy
        md = min(dl, dr, db, dt)
        if   md == dl: cx, cy = x0, gy
        elif md == dr: cx, cy = x1, gy
        elif md == db: cx, cy = gx, y0
        else:           cx, cy = gx, y1

    # Clamp to site (for blocks flush against the boundary)
    cx = max(2, min(sw - 2, cx))
    cy = max(2, min(sl - 2, cy))
    return (cx, cy)

# ── Road graph construction (Step 1.5) ────────────────────────────────────
# Graph nodes = grid cell indices (i, j). All stubs come from A* on the 2m grid,
# and road polylines are rasterised onto the same grid so they share cell nodes.

def _rasterise_polyline(grid, polyline):
    """Convert a polyline to a contiguous list of cell indices on `grid`."""
    cells = []
    half = grid.cell_size / 2
    for i in range(len(polyline) - 1):
        a = polyline[i]
        b = polyline[i + 1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < 0.001:
            continue
        n_steps = max(2, int(math.ceil(dist / half)))
        for s in range(n_steps + 1):
            t = s / n_steps
            c = grid.world_to_cell(a[0] + dx * t, a[1] + dy * t)
            if not cells or cells[-1] != c:
                cells.append(c)
    return cells


def _path_to_cells(grid, path_pts):
    """Convert a world-coord polyline (e.g. a stub) to a deduped cell sequence."""
    cells = []
    for x, y in path_pts:
        c = grid.world_to_cell(x, y)
        if not cells or cells[-1] != c:
            cells.append(c)
    return cells


def _add_cell_sequence(G, cells, road_type, grid):
    """Add consecutive cells as edges, upgrading existing edges to primary if needed."""
    for i in range(len(cells) - 1):
        a, b = cells[i], cells[i + 1]
        if a == b:
            continue
        dist = math.hypot(a[0] - b[0], a[1] - b[1]) * grid.cell_size
        if G.has_edge(a, b):
            if road_type == "primary":
                G[a][b]["road_type"] = "primary"
        else:
            G.add_edge(a, b, weight=dist, road_type=road_type)


def build_road_graph(grid, ring_road, perimeter_road, stubs, gate_pt,
                     gate_spur=None, ring_spur=None):
    """Build a networkx graph from fire roads + stub connections.

    Nodes are grid cell indices (i, j). Ring/perimeter roads, the gate spur
    (perimeter→gate), and the ring spur (ring→perimeter) are rasterised onto
    the same 2m grid as the stubs so they share cell nodes at junctions.

    Returns (G, gate_node).
    """
    G = nx.Graph()
    _add_cell_sequence(G, _rasterise_polyline(grid, ring_road),      "primary",   grid)
    for seg in perimeter_road:
        _add_cell_sequence(G, _rasterise_polyline(grid, seg), "primary",   grid)
    if gate_spur and len(gate_spur) >= 2:
        _add_cell_sequence(G, _rasterise_polyline(grid, gate_spur),  "primary",   grid)
    if ring_spur and len(ring_spur) >= 2:
        _add_cell_sequence(G, _rasterise_polyline(grid, ring_spur),  "primary",   grid)
    for block_st in stubs.values():
        for key in ("ring_stub", "perimeter_stub"):
            path = block_st.get(key, [])
            if len(path) >= 2:
                _add_cell_sequence(G, _path_to_cells(grid, path), "secondary", grid)

    gate_node = grid.world_to_cell(*gate_pt)
    if gate_node not in G:
        gate_node = min(G.nodes, key=lambda n: (n[0] - gate_node[0]) ** 2 + (n[1] - gate_node[1]) ** 2)
    return G, gate_node


def verify_and_prune(G, gate_node, stubs, grid):
    """Step 1.5: shorter-of-2 path verification + pruning.

    For each block (except Power Block) compute two candidate paths to the gate:
      - via ring_stub:      ring_stub road-side → gate (through fire road graph)
      - via perimeter_stub: perimeter_stub road-side → gate (through fire road graph)
    Compare lengths, keep only the SHORTER path, discard the longer one. The
    chosen stub is always kept (block access); the rejected stub is pruned with
    the other unused edges.

    Returns (pruned_G, used_edges_set, kept_traces).
    kept_traces is {block_name: {"via": "ring"|"perimeter", "cells": [...]}}.
    """
    used_edges = set()
    kept_traces = {}

    def _mark(a, b):
        if a != b:
            used_edges.add(tuple(sorted([a, b])))

    for block_name, block_st in stubs.items():
        if block_name == "Power Block":
            continue

        candidates = []   # list of (length_m, via_key, sp_cells, stub_cells)
        for key, via in (("ring_stub", "ring"), ("perimeter_stub", "perimeter")):
            path_pts = block_st.get(key, [])
            if len(path_pts) < 2:
                continue
            stub_cells = _path_to_cells(grid, path_pts)
            road_end = stub_cells[-1]
            if road_end not in G:
                road_end = min(G.nodes,
                               key=lambda n: (n[0] - road_end[0]) ** 2 + (n[1] - road_end[1]) ** 2)
            try:
                sp = nx.shortest_path(G, road_end, gate_node, weight="weight")
                sp_len = nx.path_weight(G, sp, weight="weight")
            except nx.NetworkXNoPath:
                continue
            # Stub length contributes too (block-side → road-side)
            stub_len = sum(math.hypot(stub_cells[i][0]-stub_cells[i-1][0],
                                      stub_cells[i][1]-stub_cells[i-1][1])
                           * grid.cell_size
                           for i in range(1, len(stub_cells)))
            candidates.append((sp_len + stub_len, via, sp, stub_cells))

        if not candidates:
            continue
        # Keep only the shortest
        candidates.sort(key=lambda c: c[0])
        _, via, sp, stub_cells = candidates[0]
        for i in range(len(sp) - 1):
            _mark(sp[i], sp[i + 1])
        for i in range(len(stub_cells) - 1):
            _mark(stub_cells[i], stub_cells[i + 1])
        kept_traces[block_name] = {"via": via, "cells": stub_cells[:-1] + sp}

    pruned = G.copy()
    to_remove = [(u, v) for u, v in pruned.edges()
                 if tuple(sorted([u, v])) not in used_edges]
    pruned.remove_edges_from(to_remove)
    pruned.remove_nodes_from(list(nx.isolates(pruned)))
    return pruned, used_edges, kept_traces


def classify_edges(G, grid):
    """Step 1.6: classify remaining edges as primary fire or secondary stub.

    Returns lists of ((x1,y1),(x2,y2)) world-coord segments.
    """
    fire_segments = []
    secondary_segs = []
    for u, v, data in G.edges(data=True):
        seg = (grid.cell_to_world(*u), grid.cell_to_world(*v))
        if data.get("road_type") == "primary":
            fire_segments.append(seg)
        else:
            secondary_segs.append(seg)
    return fire_segments, secondary_segs


# ── Main generator ────────────────────────────────────────────────────────
def generate_sketch(
    site_w, site_l, wind_dir,
    gate_side="N", gate_ratio=0.5,
    gh_edge="N",    gh_ratio=0.5,  gh_offset=0,
    bb_edge="S",
    gis_edge="N",   gis_ratio=0.8, gis_offset=0,
    water_edge="E", water_ratio=0.2, water_offset=0,
    max_pool=300,
):
    """
    Phase 06 Steps 1.1–1.3.

    Placement sequence:
      1. Fixed anchors (Gate House, GIS, RAW Water)
      2. Power Block (center ± jitter)
      3. PB Ring Road (geometry)
      4. Floated blocks (CT, WT/WWT, Warehouse, Flare, Admin, Demi Water)
      5. Perimeter Fire Road (geometry)

    Returns dict or None if no valid layout found.
    """
    sw, sl = site_w, site_l
    gate_pt = compute_gate(sw, sl, gate_side, gate_ratio)

    for _ in range(max_pool):
        placed = {}   # name → (x, y, w, h)

        # 1. Fixed anchors
        for name, edge, ratio, off in [
            ("Gate House",     gh_edge,    gh_ratio,    gh_offset),
            ("GIS",            gis_edge,   gis_ratio,   gis_offset),
            ("RAW Water Tank", water_edge, water_ratio, water_offset),
        ]:
            x, y, w, h = place_anchor(sw, sl, name, edge, ratio, off)
            placed[name] = (x, y, w, h)

        # 2. Power Block (square — rotation irrelevant)
        # Tight-site logic from Main.py: if vertical clearance on each side < 60m,
        # shift PB by exactly ±30m instead of ±5% jitter.
        pw, ph = BLOCK_FOOTPRINTS["Power Block"]
        road_w = 8
        tight_site = (sl - ph - road_w * 2) / 2 < 60
        def _pb_sample():
            cx = (sw - pw) / 2 + random.uniform(-sw * 0.05, sw * 0.05)
            if tight_site:
                cy = (sl - ph) / 2 + random.choice([-20, 20])
            else:
                cy = (sl - ph) / 2 + random.uniform(-sl * 0.05, sl * 0.05)
            m = BOUNDARY_MARGIN
            return max(m, min(cx, sw - pw - m)), max(m, min(cy, sl - ph - m))
        pb_result = _try_place(sw, sl, "Power Block", placed, _pb_sample, max_attempts=100)
        if pb_result is None:
            continue
        pb_x, pb_y, pb_w, pb_h = pb_result
        placed["Power Block"] = pb_result
        pb_cx, pb_cy = pb_x + pb_w/2, pb_y + pb_h/2

        # 3. PB Ring Road geometry + lock the road corridor for floated block placement
        ring_road = build_pb_ring_road(pb_x, pb_y, pb_w, pb_h)

        # Virtual exclusion zone to keep floated blocks exactly 8m away from the ring road centerline:
        # PB_RING_OFFSET = 8m (centerline from face) + Road Buffer = 8m (keep block 8m from centerline) = 16m total from PB face
        ring_outer = PB_RING_OFFSET + ROAD_BUFFER   # PB ring CL + road buffer
        placed["_pb_ring_zone"] = (
            pb_x - ring_outer,
            pb_y - ring_outer,
            pb_w + 2 * ring_outer,
            pb_h + 2 * ring_outer,
        )

        # 3b. Perimeter Fire Road + both spurs — built before floated blocks so
        # their 8m road buffer can act as a placement exclusion zone (otherwise
        # a floated block may land right next to a spur centerline).
        # Perimeter road is now generated later from block buffers.
        fixed_blocks_so_far = [
            {"name": n, "x": x, "y": y, "width": w, "height": h}
            for n, (x, y, w, h) in placed.items() if not n.startswith("_")
        ]
        
        bb_mid = None
        exit_helper = None
        other_corner = None
        if "Gate House" in placed:
            gh_x, gh_y, gh_w, gh_h = placed["Gate House"]
            cx, cy = gh_x + gh_w / 2, gh_y + gh_h / 2
            if bb_edge == "N":   bb_mid = (cx, gh_y + gh_h + 8)
            elif bb_edge == "S": bb_mid = (cx, gh_y - 8)
            elif bb_edge == "E": bb_mid = (gh_x + gh_w + 8, cy)
            elif bb_edge == "W": bb_mid = (gh_x - 8, cy)

            if bb_edge in ("N", "S"):
                p1 = (gh_x - 8, bb_mid[1])
                p2 = (gh_x + gh_w + 8, bb_mid[1])
                min_x, max_x = min(bb_mid[0], gate_pt[0]), max(bb_mid[0], gate_pt[0])
                p1_proj = min_x <= p1[0] <= max_x
                p2_proj = min_x <= p2[0] <= max_x
                if p1_proj and not p2_proj:
                    exit_helper, other_corner = p2, p1
                elif p2_proj and not p1_proj:
                    exit_helper, other_corner = p1, p2
                else:
                    if abs(p1[0] - sw/2) < abs(p2[0] - sw/2):
                        exit_helper, other_corner = p1, p2
                    else:
                        exit_helper, other_corner = p2, p1
            else:
                p1 = (bb_mid[0], gh_y - 8)
                p2 = (bb_mid[0], gh_y + gh_h + 8)
                min_y, max_y = min(bb_mid[1], gate_pt[1]), max(bb_mid[1], gate_pt[1])
                p1_proj = min_y <= p1[1] <= max_y
                p2_proj = min_y <= p2[1] <= max_y
                if p1_proj and not p2_proj:
                    exit_helper, other_corner = p2, p1
                elif p2_proj and not p1_proj:
                    exit_helper, other_corner = p1, p2
                else:
                    if abs(p1[1] - sl/2) < abs(p2[1] - sl/2):
                        exit_helper, other_corner = p1, p2
                    else:
                        exit_helper, other_corner = p2, p1

        if bb_mid and exit_helper and other_corner:
            # Calculate Gate Death Zone
            if bb_edge in ("N", "S"):
                gdz_x_min = bb_mid[0] if other_corner[0] >= bb_mid[0] else 0
                gdz_x_max = sw if other_corner[0] >= bb_mid[0] else bb_mid[0]
                gdz_y_min = bb_mid[1] if gate_pt[1] >= bb_mid[1] else 0
                gdz_y_max = sl if gate_pt[1] >= bb_mid[1] else bb_mid[1]
            else:
                gdz_x_min = bb_mid[0] if gate_pt[0] >= bb_mid[0] else 0
                gdz_x_max = sw if gate_pt[0] >= bb_mid[0] else bb_mid[0]
                gdz_y_min = bb_mid[1] if other_corner[1] >= bb_mid[1] else 0
                gdz_y_max = sl if other_corner[1] >= bb_mid[1] else bb_mid[1]
            gate_death_zone = (gdz_x_min, gdz_y_min, gdz_x_max - gdz_x_min, gdz_y_max - gdz_y_min)
            placed["_gate_death_zone"] = gate_death_zone

            dummy_ring_spur = build_ring_spur(sw, sl, ring_road, fixed_blocks_so_far, exit_helper)
            pt_on_ring = dummy_ring_spur[0]
            
            if gate_side in ("N", "S"):
                ring_spur = [pt_on_ring, (pt_on_ring[0], exit_helper[1]), exit_helper]
            else:
                ring_spur = [pt_on_ring, (exit_helper[0], pt_on_ring[1]), exit_helper]
                
            if bb_edge in ("N", "S"):
                gate_spur = [exit_helper, bb_mid, other_corner, (other_corner[0], gate_pt[1]), gate_pt]
            else:
                gate_spur = [exit_helper, bb_mid, other_corner, (gate_pt[0], other_corner[1]), gate_pt]
        else:
            gate_death_zone = None
            gate_spur = build_gate_spur(sw, sl, gate_pt)
            ring_spur = build_ring_spur(sw, sl, ring_road, fixed_blocks_so_far, gate_pt)
        for zone_name, line in (("_gate_spur_zone", gate_spur),
                                ("_ring_spur_zone", ring_spur)):
            rect = _spur_exclusion_rect(line, buffer=ROAD_BUFFER)
            if rect:
                placed[zone_name] = rect

        # 4. Floated blocks — magnet placement with zone rules.
        gh_x, gh_y = placed["Gate House"][:2]
        admin_anchor = ((gh_x + pb_cx) / 2, (gh_y + pb_cy) / 2)
        raw_x, raw_y, raw_w, raw_h = placed["RAW Water Tank"]
        raw_cx, raw_cy = raw_x + raw_w/2, raw_y + raw_h/2

        def leeward_filter(x, y, w, h):
            if wind_dir == "East": return x <= sw * 0.45
            if wind_dir == "West": return x >= sw * 0.55
            if wind_dir == "North": return y <= sl * 0.45
            return y >= sl * 0.55

        def near_raw_filter(x, y, w, h):
            cx, cy = x + w/2, y + h/2
            return (cx - raw_cx)**2 + (cy - raw_cy)**2 <= 150**2

        if wind_dir == "East": flare_corner = (0, sl/2)
        elif wind_dir == "West": flare_corner = (sw, sl/2)
        elif wind_dir == "North": flare_corner = (sw/2, 0)
        else: flare_corner = (sw/2, sl)

        floated_order = [
            ("Cooling Tower",   (pb_cx, pb_cy),   leeward_filter,  "Power Block"),
            ("WT/WWT",          (pb_cx, pb_cy),   near_raw_filter, "Power Block"),
            ("Warehouse",       None,             None,            "Power Block"),
            ("Flare",           flare_corner,     leeward_filter,  None),
            ("Admin Building",  admin_anchor,     None,            "Power Block"),
            ("Demi Water Tank", (raw_cx, raw_cy), near_raw_filter, "RAW Water Tank"),
        ]

        ok = True
        for name, prefer, f_fn, m_target in floated_order:
            pos = _try_magnet_place(sw, sl, name, placed, prefer_near=prefer, filter_fn=f_fn, magnet_target=m_target)
            if pos is None:
                ok = False
                break
            placed[name] = pos
        if not ok:
            continue

        # Build output — filter out internal virtual zones (names starting with '_')
        blocks = [
            {"name": n, "x": x, "y": y, "width": w, "height": h,
             "color": BLOCK_COLORS.get(n, "#aaaaaa"),
             "rotated": (w, h) != BLOCK_FOOTPRINTS.get(n, (w, h))}
            for n, (x, y, w, h) in placed.items()
            if not n.startswith("_")
        ]

        # 4. RACK placement (Step 1.2-RACK) — comes AFTER floated blocks but
        # BEFORE perimeter/spurs/stubs (racks are more important than roads).
        # Step A: per-block buffer rectangles for Case 1 & Case 2 layouts.
        # Steps B-1..B-5 and C (spine + connector) — not implemented yet.
        rack_buffers = compute_rack_buffers(blocks)
        spine_centerlines, candidate_points, active_cases, water_triangle = build_rack_spines(rack_buffers, blocks, sw, sl)
        pb_ct_segments = list(spine_centerlines)
        water_cluster_segments = []
        rack_segments = list(spine_centerlines)

        valid_xs = set()
        valid_ys = set()
        for b_name in RACK_BLOCKS:
            if b_name in rack_buffers and b_name in active_cases:
                rx, ry, rw, rh = rack_buffers[b_name][active_cases[b_name]]
                valid_xs.update([rx, rx+rw])
                valid_ys.update([ry, ry+rh])
        for pt in water_triangle:
            valid_xs.add(pt[0])
            valid_ys.add(pt[1])
        for seg in pb_ct_segments:
            valid_xs.update([seg[0][0], seg[1][0]])
            valid_ys.update([seg[0][1], seg[1][1]])

        flare_b = next((b for b in blocks if b["name"] == "Flare"), None)
        if flare_b:
            f_off = RACK_CASE1_OFFSET
            valid_xs.update([flare_b["x"] - f_off, flare_b["x"] + flare_b["width"] + f_off])
            valid_ys.update([flare_b["y"] - f_off, flare_b["y"] + flare_b["height"] + f_off])

        def snap_pt(px, py):
            best_x, best_y = px - CELL_SIZE / 2, py - CELL_SIZE / 2
            min_dx, min_dy = 1.5, 1.5
            for vx in valid_xs:
                if abs(vx - px) < min_dx:
                    min_dx = abs(vx - px)
                    best_x = vx
            for vy in valid_ys:
                if abs(vy - py) < min_dy:
                    min_dy = abs(vy - py)
                    best_y = vy
            return (best_x, best_y)

        # B-5: Water cluster spine
        if len(water_triangle) == 3:
            grid_b5 = Grid(sw, sl, cell_size=CELL_SIZE)
            for b in blocks:
                grid_b5.mark_building(b, inflate_m=0)
                
            def astar_route(p1, p2):
                c1 = grid_b5.world_to_cell(*p1)
                c2 = grid_b5.world_to_cell(*p2)
                was1 = grid_b5.blocked[c1]
                was2 = grid_b5.blocked[c2]
                grid_b5.blocked[c1] = False
                grid_b5.blocked[c2] = False
                path = astar(grid_b5, c1, c2, width_cells=0, allow_diagonal=False)
                grid_b5.blocked[c1] = was1
                grid_b5.blocked[c2] = was2
                return [snap_pt(*grid_b5.cell_to_world(*c)) for c in path] if path else []
                
            raw_pt, demi_pt, wwt_pt = water_triangle[0], water_triangle[1], water_triangle[2]
            
            path_rd = astar_route(raw_pt, demi_pt)
            path_rw = astar_route(raw_pt, wwt_pt)
            path_dw = astar_route(demi_pt, wwt_pt)
            
            len_rd = len(path_rd) if path_rd else float('inf')
            len_rw = len(path_rw) if path_rw else float('inf')
            len_dw = len(path_dw) if path_dw else float('inf')
            
            paths = [(len_rd, path_rd), (len_rw, path_rw), (len_dw, path_dw)]
            paths.sort(key=lambda x: x[0])
            
            for length, path in paths[:2]:
                if length != float('inf') and path:
                    simplified = [path[0]]
                    for i in range(1, len(path)-1):
                        p0, p1, p2 = simplified[-1], path[i], path[i+1]
                        if not (p0[0] == p1[0] == p2[0] or p0[1] == p1[1] == p2[1]):
                            simplified.append(p1)
                    simplified.append(path[-1])
                    for i in range(len(simplified)-1):
                        seg = [simplified[i], simplified[i+1]]
                        rack_segments.append(seg)
                        water_cluster_segments.append(seg)

        # Step C: Connect spines into one network
        if len(spine_centerlines) >= 2 and water_cluster_segments:
            pb_line = [spine_centerlines[0]]
            ct_line = [spine_centerlines[1]]
            grid_c = Grid(sw, sl, cell_size=CELL_SIZE)
            
            def set_segment_blocked(p1, p2, val):
                c1 = grid_c.world_to_cell(*p1)
                c2 = grid_c.world_to_cell(*p2)
                if c1[0] == c2[0]:
                    for y in range(min(c1[1], c2[1]), max(c1[1], c2[1]) + 1):
                        grid_c.blocked[c1[0], y] = val
                elif c1[1] == c2[1]:
                    for x in range(min(c1[0], c2[0]), max(c1[0], c2[0]) + 1):
                        grid_c.blocked[x, c1[1]] = val

            def set_extended_line_blocked(p1, p2, val):
                c1 = grid_c.world_to_cell(*p1)
                c2 = grid_c.world_to_cell(*p2)
                if c1[0] == c2[0]:
                    for y in range(grid_c.nrows):
                        grid_c.blocked[c1[0], y] = val
                elif c1[1] == c2[1]:
                    for x in range(grid_c.ncols):
                        grid_c.blocked[x, c1[1]] = val

            def route_between(source_segments, target_segments):
                def run_routing(restricted):
                    if restricted:
                        grid_c.blocked[:, :] = True
                        for seg in pb_line + ct_line + water_cluster_segments:
                            set_extended_line_blocked(seg[0], seg[1], False)
                        for b_name in RACK_BLOCKS:
                            if b_name in rack_buffers and b_name in active_cases:
                                rx, ry, rw, rh = rack_buffers[b_name][active_cases[b_name]]
                                set_segment_blocked((rx, ry), (rx+rw, ry), False)
                                set_segment_blocked((rx+rw, ry), (rx+rw, ry+rh), False)
                                set_segment_blocked((rx, ry+rh), (rx+rw, ry+rh), False)
                                set_segment_blocked((rx, ry), (rx, ry+rh), False)
                    else:
                        grid_c.blocked[:, :] = False

                    for b in blocks:
                        grid_c.mark_building(b, inflate_m=0)

                    start_cells = []
                    for seg in source_segments:
                        c1 = grid_c.world_to_cell(*seg[0])
                        c2 = grid_c.world_to_cell(*seg[1])
                        if c1[0] == c2[0]:
                            for y in range(min(c1[1], c2[1]), max(c1[1], c2[1]) + 1):
                                if not grid_c.blocked[c1[0], y]:
                                    start_cells.append((c1[0], y))
                        else:
                            for x in range(min(c1[0], c2[0]), max(c1[0], c2[0]) + 1):
                                if not grid_c.blocked[x, c1[1]]:
                                    start_cells.append((x, c1[1]))
                    
                    goal_cells = set()
                    for seg in target_segments:
                        c1 = grid_c.world_to_cell(*seg[0])
                        c2 = grid_c.world_to_cell(*seg[1])
                        if c1[0] == c2[0]:
                            for y in range(min(c1[1], c2[1]), max(c1[1], c2[1]) + 1):
                                if not grid_c.blocked[c1[0], y]:
                                    goal_cells.add((c1[0], y))
                        else:
                            for x in range(min(c1[0], c2[0]), max(c1[0], c2[0]) + 1):
                                if not grid_c.blocked[x, c1[1]]:
                                    goal_cells.add((x, c1[1]))

                    import collections
                    queue = collections.deque()
                    visited = {}
                    for sc in start_cells:
                        queue.append(sc)
                        visited[sc] = None
                    
                    found_goal = None
                    while queue:
                        curr = queue.popleft()
                        if curr in goal_cells:
                            found_goal = curr
                            break
                        cx, cy = curr
                        for dx, dy in [(0,1), (1,0), (0,-1), (-1,0)]:
                            nx, ny = cx + dx, cy + dy
                            if 0 <= nx < grid_c.ncols and 0 <= ny < grid_c.nrows:
                                if not grid_c.blocked[nx, ny]:
                                    if (nx, ny) not in visited:
                                        visited[(nx, ny)] = curr
                                        queue.append((nx, ny))
                    return found_goal, visited

                found_goal, visited = run_routing(restricted=True)
                if not found_goal:
                    found_goal, visited = run_routing(restricted=False)

                if found_goal:
                    path_cells = []
                    curr = found_goal
                    while curr is not None:
                        path_cells.append(curr)
                        curr = visited[curr]
                    path_cells.reverse()

                    if len(path_cells) > 1:
                        path_pts = [snap_pt(*grid_c.cell_to_world(*c)) for c in path_cells]
                        simplified = [path_pts[0]]
                        for i in range(1, len(path_pts)-1):
                            p0, p1, p2 = simplified[-1], path_pts[i], path_pts[i+1]
                            if not (p0[0] == p1[0] == p2[0] or p0[1] == p1[1] == p2[1]):
                                simplified.append(p1)
                        simplified.append(path_pts[-1])
                        new_segs = []
                        for i in range(len(simplified)-1):
                            seg = [simplified[i], simplified[i+1]]
                            rack_segments.append(seg)
                            new_segs.append(seg)
                        return found_goal, new_segs
                return None, []

            # 1. water cluster spine to closest line (CT line or PB line)
            found_goal_1, new_segs_1 = route_between(water_cluster_segments, pb_line + ct_line)
            water_cluster_segments.extend(new_segs_1)
            
            if found_goal_1:
                def is_in_segments(cell, segments):
                    for seg in segments:
                        c1 = grid_c.world_to_cell(*seg[0])
                        c2 = grid_c.world_to_cell(*seg[1])
                        if c1[0] == c2[0] and min(c1[1], c2[1]) <= cell[1] <= max(c1[1], c2[1]) and c1[0] == cell[0]:
                            return True
                        if c1[1] == c2[1] and min(c1[0], c2[0]) <= cell[0] <= max(c1[0], c2[0]) and c1[1] == cell[1]:
                            return True
                    return False
                
                # 2. connect with rest line block (CT or PB)
                if is_in_segments(found_goal_1, pb_line):
                    route_between(water_cluster_segments + pb_line, ct_line)
                else:
                    route_between(water_cluster_segments + ct_line, pb_line)

            # Step C-2: Flare Pipe Rack
            flare_block = next((b for b in blocks if b["name"] == "Flare"), None)
            if flare_block:
                fx, fy, fw, fh = flare_block["x"], flare_block["y"], flare_block["width"], flare_block["height"]
                flare_offset = RACK_CASE1_OFFSET
                fx0, fy0 = fx - flare_offset, fy - flare_offset
                fx1, fy1 = fx + fw + flare_offset, fy + fh + flare_offset
                
                def touches_flare(segments):
                    for p1, p2 in segments:
                        sxmin, sxmax = min(p1[0], p2[0]), max(p1[0], p2[0])
                        symin, symax = min(p1[1], p2[1]), max(p1[1], p2[1])
                        if sxmax < fx0 or sxmin > fx1: continue
                        if symax < fy0 or symin > fy1: continue
                        return True
                    return False

                if not touches_flare(rack_segments):
                    flare_corners = [(fx0, fy0), (fx1, fy0), (fx1, fy1), (fx0, fy1)]
                    flare_corner_segs = [[c, c] for c in flare_corners]
                    route_between(flare_corner_segs, rack_segments)

                # Add to rack_buffers for dashboard visualization
                rack_buffers["Flare"] = {"case1_rack": (fx0, fy0, fw + 2 * flare_offset, fh + 2 * flare_offset)}

        perimeter_segments = generate_perimeter_segments(placed, pb_cx, pb_cy)

        # 6. Obstacle-avoiding connection stubs (Step 1.4)
        # Inflate OTHER blocks so their road buffer is treated as an obstacle.
        # Use ROAD_BUFFER - 1m (cell quantization slack) on the 2m grid: a path
        # is allowed to run ON the road-buffer line, so the cell whose center
        # is exactly ROAD_BUFFER from the block edge must be free.
        ROUTE_INFLATE = ROAD_BUFFER - 1
        stubs = {}
        for b in blocks:
            if b["name"] == "Gate House":
                continue

            grid = Grid(sw, sl, cell_size=CELL_SIZE)
            for other in blocks:
                if other["name"] != b["name"]:
                    grid.mark_building(other, inflate_m=ROUTE_INFLATE)

            bx, by, bw, bh = b["x"], b["y"], b["width"], b["height"]
            bc = (bx + bw/2, by + bh/2)

            pt_ring = find_nearest_road_point(bc, ring_road)
            pt_peri = find_nearest_road_point(bc, perimeter_segments)

            block_stubs = {}
            for road_name, goal_pt, key in [("Ring Road", pt_ring, "ring_stub"), ("Perimeter Road", pt_peri, "perimeter_stub")]:
                # Deterministic start: the geometric closest point on this
                # block's road-buffer outline to the goal road anchor. Ring
                # stub starts on the PB-facing side; perimeter stub on the
                # perimeter side. Not restricted to N/S/E/W midpoints — can
                # land on any edge or corner of the buffer rectangle.
                best_cand = closest_buffer_point(b, goal_pt, sw, sl, offset=ROAD_BUFFER)
                start_cell = grid.world_to_cell(*best_cand)
                goal_cell  = grid.world_to_cell(*goal_pt)

                was_blocked_start = grid.blocked[start_cell]
                was_blocked_goal  = grid.blocked[goal_cell]
                grid.blocked[start_cell] = False
                grid.blocked[goal_cell]  = False

                # 4-connected only: roads run in straight (axis-aligned) segments,
                # no diagonal moves.
                path = astar(grid, start_cell, goal_cell, width_cells=0,
                             allow_diagonal=False)

                grid.blocked[start_cell] = was_blocked_start
                grid.blocked[goal_cell]  = was_blocked_goal

                if path:
                    # Use raw cell-center coords — keeps every segment
                    # axis-aligned. Endpoints sit at the cell center (≤1m
                    # offset from the actual buffer point / road CL).
                    block_stubs[key] = [grid.cell_to_world(*c) for c in path]
                else:
                    # Fallback: direct line from chosen candidate (may be
                    # diagonal — only happens when A* finds no path).
                    block_stubs[key] = [best_cand, goal_pt]

            stubs[b["name"]] = block_stubs

        # Gate House sits on the perimeter — give it a short axis-aligned stub
        # from a side-buffer point to the perimeter CL so it shows up in the
        # kept road graph (not just in path_traces).
        gh = next((b for b in blocks if b["name"] == "Gate House"), None)
        if gh is not None:
            bx, by, bw, bh = gh["x"], gh["y"], gh["width"], gh["height"]
            cx, cy = bx + bw / 2, by + bh / 2
            # Which boundary the GH sits flush against:
            if   by + bh >= sl - 0.01: side = "N"
            elif by <= 0.01:           side = "S"
            elif bx + bw >= sw - 0.01: side = "E"
            elif bx <= 0.01:           side = "W"
            else:                       side = "N"
            # Pick a side buffer edge perpendicular to that boundary, then drop
            # axis-aligned onto the perimeter CL.
            if side in ("N", "S"):
                buf_x = bx + bw + ROAD_BUFFER if bx + bw + ROAD_BUFFER < sw - 2 else bx - ROAD_BUFFER
                peri_y = sl - PERIMETER_CL_DIST if side == "N" else PERIMETER_CL_DIST
                gh_stub = [(buf_x, cy), (buf_x, peri_y)]
            else:
                buf_y = by + bh + ROAD_BUFFER if by + bh + ROAD_BUFFER < sl - 2 else by - ROAD_BUFFER
                peri_x = sw - PERIMETER_CL_DIST if side == "E" else PERIMETER_CL_DIST
                gh_stub = [(cx, buf_y), (peri_x, buf_y)]
            stubs["Gate House"] = {"ring_stub": [], "perimeter_stub": gh_stub}

        group_a_segments = generate_group_a_access(placed, sw, sl, gate_pt[0], gate_pt[1])

        # 7. Road graph (no pruning, per user request)
        graph_grid = Grid(sw, sl, cell_size=CELL_SIZE)
        road_graph, gate_node = build_road_graph(
            graph_grid, ring_road, perimeter_segments, stubs, gate_pt,
            gate_spur=gate_spur, ring_spur=ring_spur,
        )
        pruned_graph = road_graph
        _, secondary_segs = classify_edges(pruned_graph, graph_grid)
        
        # Override rasterized primary roads with exact vector polylines
        # to prevent the 1m visual quantization offset on the 2m grid.
        fire_segments = []
        for poly in (ring_road, gate_spur, ring_spur):
            if poly:
                for i in range(len(poly) - 1):
                    fire_segments.append((poly[i], poly[i+1]))
        for seg in perimeter_segments:
            fire_segments.append(seg)

        pruned_segments = []
        path_traces = []

        # Boom Barrier: 16m line from the Gate House inner edge pointing inwards
        boom_barrier = []
        if gh is not None:
            bx, by, bw, bh = gh["x"], gh["y"], gh["width"], gh["height"]
            cx, cy = bx + bw / 2, by + bh / 2
            if bb_edge == "N":   boom_barrier = [(cx, by + bh), (cx, by + bh + 16)]
            elif bb_edge == "S": boom_barrier = [(cx, by), (cx, by - 16)]
            elif bb_edge == "E": boom_barrier = [(bx + bw, cy), (bx + bw + 16, cy)]
            elif bb_edge == "W": boom_barrier = [(bx, cy), (bx - 16, cy)]

        # ---------------------------------------------------------------------
        # Final Assembly
        # ---------------------------------------------------------------------
        return {
            "blocks":          blocks,
            "boom_barrier":    boom_barrier,
            "ring_road":       ring_road,
            "perimeter_segments": perimeter_segments,
            "group_a_segments": group_a_segments,
            "gate_spur":       gate_spur,
            "ring_spur":       ring_spur,
            "rack_buffers":    rack_buffers,
            "rack_segments":   rack_segments,
            "rack_candidates": candidate_points,
            "active_rack_cases": active_cases,
            "water_triangle":  water_triangle,
            "stubs":           stubs,
            "road_graph":      pruned_graph,
            "fire_segments":   fire_segments,
            "secondary_segs":  secondary_segs,
            "pruned_segments": pruned_segments,
            "path_traces":     path_traces,
            "gate_point":      gate_pt,
            "gate_death_zone": gate_death_zone,
            "gate_node":       gate_node,
            "pb_center":       (pb_cx, pb_cy),
            "cell_size":       CELL_SIZE,
            "block_buffer":    BLOCK_BUFFER,
            "pb_ring_offset":  PB_RING_OFFSET,
            "perimeter_cl":    PERIMETER_CL_DIST,
        }

    return None

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
BOUNDARY_TOLERANCE = 10  # unified boundary leeway: PB/anchor clamp margin AND floated-block spillage
PB_RING_OFFSET    = 16   # ring CL from PB face — 16m for rack block road buffer
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
ROAD_W_RACK_OFFSET   = 16   # road CL on a side that has a rack
B2B_W_RACK_OFFSET    = 30   # block-to-block on a side that has a rack
RACK_CASE1_OFFSET    = 8
RACK_CASE2_OFFSET    = 24

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
def snap(v):  # → §2
    return round(v / CELL_SIZE) * CELL_SIZE

def snap_xy(x, y):  # → §2
    return snap(x), snap(y)

# ── Overlap check ──────────────────────────────────────────────────────────
def _overlaps(ax, ay, aw, ah, bx, by, bw, bh, gap=BLOCK_BUFFER):  # → §3.5.B
    return not (ax + aw + gap <= bx or bx + bw + gap <= ax or
                ay + ah + gap <= by or by + bh + gap <= ay)


def pair_min_gap(name_a, name_b):  # → §3.5.B
    """Minimum allowed edge-to-edge distance between two real blocks.

    Keyed on rack membership (`RACK_BLOCKS`):
      rack ↔ rack       → ROAD_W_RACK_OFFSET (14m, shared rack-side road CL)
      no-rack ↔ no-rack → ROAD_BUFFER       (8m, shared no-rack road CL)
      mixed             → B2B_W_RACK_OFFSET (28m, rack-side b2b)

    Virtual `_…_zone` entries are handled by the caller (gap=0)."""
    a_rack = name_a in RACK_BLOCKS
    b_rack = name_b in RACK_BLOCKS
    
    a_offset = 16 if name_a == "Gate House" else (ROAD_W_RACK_OFFSET if a_rack else ROAD_BUFFER)
    b_offset = 16 if name_b == "Gate House" else (ROAD_W_RACK_OFFSET if b_rack else ROAD_BUFFER)
    
    return a_offset + b_offset


def _overlaps_any(name, placed, x, y, w, h):  # → §3.5.B
    """Per-pair edge-to-edge gap, keyed on rack membership via `pair_min_gap`.

    Virtual zones (names with `_` prefix — `_pb_ring_zone`, `_gate_spur_zone`,
    `_ring_spur_zone`) use gap=0 because their rectangle already includes the
    8m road buffer; a block touching the zone edge is already 8m from the
    road centerline."""
    for bname, (bx, by, bw, bh) in placed.items():
        if bname == "_gate_death_zone" and name in ("Cooling Tower", "WT/WWT", "Warehouse", "Flare", "Admin Building", "Demi Water Tank"):
            continue
        current_gap = 0 if bname.startswith("_") else pair_min_gap(name, bname)
        if _overlaps(x, y, w, h, bx, by, bw, bh, current_gap):
            return True
    return False


def _within_relaxed_bounds(x, y, w, h, sw, sl, tol=BOUNDARY_TOLERANCE):  # → §3.5.A
    """Allow placement up to `tol` metres outside the plot on any side."""
    return (x >= -tol and y >= -tol
            and x + w <= sw + tol and y + h <= sl + tol)

# ── Placement helpers ──────────────────────────────────────────────────────
def place_anchor(sw, sl, name, edge, ratio, offset, jitter=0.0):  # → §3.2
    """Fixed anchor — grid-snapped. Returns (x, y, w, h).

    `jitter` (fraction, e.g. 0.05) lets the anchor wander up to ±jitter of the
    site dimension around its fixed position — along the sliding axis (x for
    N/S edges, y for E/W edges). 0 keeps the legacy exact placement."""
    w, h = BLOCK_FOOTPRINTS[name]
    if   edge == "N": x, y = (sw - w) * ratio, sl - h - offset
    elif edge == "S": x, y = (sw - w) * ratio, offset
    elif edge == "E": x, y = sw - w - offset,  (sl - h) * ratio
    elif edge == "W": x, y = offset,            (sl - h) * ratio
    else: raise ValueError(f"edge must be N/S/E/W, got {edge!r}")
    if jitter:
        if edge in ("N", "S"):
            x += random.uniform(-sw * jitter, sw * jitter)
        else:
            y += random.uniform(-sl * jitter, sl * jitter)
    x, y = snap_xy(x, y)
    return max(0, min(x, sw - w)), max(0, min(y, sl - h)), w, h


def _try_place(sw, sl, name, placed, sample_fn, max_attempts=500, prefer_near=None, buffer=0,  # → §3.3
               x_bounds=None, y_bounds=None):
    """
    Try to place block using sample_fn() → (x, y).
    Tries BOTH orientations (w×h and h×w) at each sampled point.
    Uses name-aware gap exceptions (RAW Water Tank neighbors get 3m gap).
    prefer_near: optional (cx, cy) — selects from top 10% closest (matches Main.py).
    buffer: inflate the block by this much when clamping to plot bounds, so the
            block's *road buffer geometry* (not bare footprint) must stay inside
            the plot. Inter-block gaps are already handled by pair_min_gap.
    x_bounds / y_bounds: optional (lo, hi) explicit clamp range for the block
            ORIGIN. When given, overrides the default boundary-margin clamp on
            that axis (used to stop PB at the gate-house line on the gate side).
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
            # Clamp so the BUFFERED rectangle (block + road buffer) stays
            # BOUNDARY_TOLERANCE inside every site edge — unless an explicit
            # per-axis bound is supplied (gate-side stop line).
            m = BOUNDARY_TOLERANCE + buffer
            xlo, xhi = x_bounds if x_bounds else (m, sw - w - m)
            ylo, yhi = y_bounds if y_bounds else (m, sl - h - m)
            x = max(xlo, min(x, xhi))
            y = max(ylo, min(y, yhi))
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
def _slide(t_start, t_extent, b_extent, inset, i, n):  # → §3.5
    """i-th of n evenly spaced lateral positions for a block of extent
    `b_extent` sliding along a target's side of extent `t_extent`. `inset`
    forces a minimum corner overlap so candidates are not perfectly flush
    with the target's corner (avoids 0-overlap degenerate adjacency)."""
    lo = t_start - b_extent + inset
    hi = t_start + t_extent - inset
    if n <= 1:
        return (lo + hi) / 2
    return lo + (hi - lo) * i / (n - 1)


def _magnet_candidates(name, w, h, placed, sw, sl,  # → §3.5
                       samples_per_side=7, lateral_inset=4, target=None, boundary_tol=BOUNDARY_TOLERANCE):
    """Generate (x, y) candidates by snapping a block (w×h, named `name`) at
    the pair-appropriate magnet distance against each side of every real
    placed block. Honors relaxed bounds (`_within_relaxed_bounds`) and the
    per-pair collision check (`_overlaps_any`)."""
    cands = []
    for tname, bounds in placed.items():
        if tname.startswith("_"):
            continue
        tx, ty, tw, th = bounds
        if target is not None and tname != target:
            continue
        # Do not use fixed anchors or Flare as default magnets unless explicitly targeted
        if target is None and tname in ("Gate House", "GIS", "RAW Water Tank", "Flare"):
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
            if not _within_relaxed_bounds(x, y, w, h, sw, sl, tol=boundary_tol):
                continue
            if _overlaps_any(name, placed, x, y, w, h):
                continue
            cands.append((x, y))
    return cands


def _try_magnet_place(sw, sl, name, placed, prefer_near=None, filter_fn=None, magnet_target=None,  # → §3.5
                      boundary_tol=BOUNDARY_TOLERANCE):
    """Place a floated block by magnetizing to a previously placed block.

    Tries both orientations. Returns (x, y, w, h) or None when no candidate
    survives bounds + collision checks. `prefer_near` keeps the existing
    top-10%-closest selection so blocks still cluster near PB. `filter_fn`
    can be used to restrict placement to specific zones (e.g. Leeward).
    `boundary_tol` controls how far outside the plot boundary candidates may sit."""
    base_w, base_h = BLOCK_FOOTPRINTS[name]
    orientations = [(base_w, base_h)]
    if base_w != base_h:
        orientations.append((base_h, base_w))

    valid = []
    for w, h in orientations:
        for x, y in _magnet_candidates(name, w, h, placed, sw, sl, target=magnet_target,
                                       boundary_tol=boundary_tol):
            if filter_fn is None or filter_fn(x, y, w, h):
                valid.append((x, y, w, h))

    # Fallback to any valid magnet target if the specified target fails
    if magnet_target is not None and not valid:
        for w, h in orientations:
            for x, y in _magnet_candidates(name, w, h, placed, sw, sl, target=None,
                                           boundary_tol=boundary_tol):
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
def build_pb_ring_road(pb_x, pb_y, pb_w, pb_h, offset=PB_RING_OFFSET):  # → §3.4.A
    """Closed polyline of PB ring road centerline."""
    x1, y1 = pb_x - offset, pb_y - offset
    x2, y2 = pb_x + pb_w + offset, pb_y + pb_h + offset
    return [(x1,y1),(x2,y1),(x2,y2),(x1,y2),(x1,y1)]



def compute_unsnapped_buffers(placed):
    buffers = {}
    for name, bounds in placed.items():
        if name.startswith("_"):
            if name == "_gate_death_zone":
                offset = 8
                x, y, w, h = bounds
                buffers[name] = (x - offset, y - offset, w + 2*offset, h + 2*offset)
            continue
        offset = 16 if name in RACK_BLOCKS else 8
        x, y, w, h = bounds
        buffers[name] = (x - offset, y - offset, w + 2*offset, h + 2*offset)
    return buffers


def compute_buffer_union_contour(computed_buffers, sw, sl):
    # Include all blocks to ensure the perimeter road doesn't cut through them
    filtered_buffers = {name: b for name, b in computed_buffers.items() if not name.startswith("_") or name == "_gate_death_zone"}
    
    TOL = 0.1
    if not filtered_buffers: return [], {}
    
    # 1. Base grid bounds
    min_x = min(b[0] for b in filtered_buffers.values())
    min_y = min(b[1] for b in filtered_buffers.values())
    max_x = max(b[0] + b[2] for b in filtered_buffers.values())
    max_y = max(b[1] + b[3] for b in filtered_buffers.values())
    
    RES = 0.5
    K_m = 100 # 100m closing radius -> bridges gaps up to 200m to ensure NO isolated blocks
    K = int(K_m / RES)
    
    # Pad grid by K + 5 cells to prevent morphological edge effects
    min_x -= (K_m + 5)
    min_y -= (K_m + 5)
    max_x += (K_m + 5)
    max_y += (K_m + 5)
    
    w_cells = int((max_x - min_x) / RES)
    h_cells = int((max_y - min_y) / RES)
    grid = [[0]*w_cells for _ in range(h_cells)]
    
    # 2. Paint blocks
    for name, (bx, by, bw, bh) in filtered_buffers.items():
        ix0, iy0 = int((bx - min_x) / RES), int((by - min_y) / RES)
        ix1, iy1 = int((bx + bw - min_x) / RES), int((by + bh - min_y) / RES)
        for y in range(max(0,iy0), min(h_cells,iy1)):
            for x in range(max(0,ix0), min(w_cells,ix1)):
                grid[y][x] = 1
                
    # 3. Morphological Closing (Dilate -> Erode)
    # Dilate
    d_grid = [[0]*w_cells for _ in range(h_cells)]
    for y in range(h_cells):
        count = 0
        for x in range(w_cells):
            if grid[y][x]: count = K + 1
            elif count > 0: count -= 1
            if count > 0: d_grid[y][x] = 1
        count = 0
        for x in range(w_cells-1, -1, -1):
            if grid[y][x]: count = K + 1
            elif count > 0: count -= 1
            if count > 0: d_grid[y][x] = 1
            
    d2_grid = [[0]*w_cells for _ in range(h_cells)]
    for x in range(w_cells):
        count = 0
        for y in range(h_cells):
            if d_grid[y][x]: count = K + 1
            elif count > 0: count -= 1
            if count > 0: d2_grid[y][x] = 1
        count = 0
        for y in range(h_cells-1, -1, -1):
            if d_grid[y][x]: count = K + 1
            elif count > 0: count -= 1
            if count > 0: d2_grid[y][x] = 1
            
    # Erode (Dilate the 0s)
    e_grid = [[1]*w_cells for _ in range(h_cells)]
    for y in range(h_cells):
        count = 0
        for x in range(w_cells):
            if not d2_grid[y][x]: count = K + 1
            elif count > 0: count -= 1
            if count > 0: e_grid[y][x] = 0
        count = 0
        for x in range(w_cells-1, -1, -1):
            if not d2_grid[y][x]: count = K + 1
            elif count > 0: count -= 1
            if count > 0: e_grid[y][x] = 0
            
    e2_grid = [[1]*w_cells for _ in range(h_cells)]
    for x in range(w_cells):
        count = 0
        for y in range(h_cells):
            if not e_grid[y][x]: count = K + 1
            elif count > 0: count -= 1
            if count > 0: e2_grid[y][x] = 0
        count = 0
        for y in range(h_cells-1, -1, -1):
            if not e_grid[y][x]: count = K + 1
            elif count > 0: count -= 1
            if count > 0: e2_grid[y][x] = 0

    # Create a routing dent for Gate House and Gate Death Zone
    for name, b in computed_buffers.items():
        if name == "_gate_death_zone":
            cx0, cy0, cw, ch = b
            # b already has 8m buffer.
            x0, y0 = int((cx0 - min_x)/RES), int((cy0 - min_y)/RES)
            x1, y1 = int((cx0 + cw - min_x)/RES), int((cy0 + ch - min_y)/RES)
            for y in range(max(0, y0), min(h_cells, y1)):
                for x in range(max(0, x0), min(w_cells, x1)):
                    e2_grid[y][x] = 0
        elif name == "Gate House":
            cx0, cy0, cw, ch = b
            # Expand by another 8m to ensure 16m buffer (keeps road 8m away from 8m corners)
            cx0 -= 8; cy0 -= 8; cw += 16; ch += 16
            x0, y0 = int((cx0 - min_x)/RES), int((cy0 - min_y)/RES)
            x1, y1 = int((cx0 + cw - min_x)/RES), int((cy0 + ch - min_y)/RES)
            for y in range(max(0, y0), min(h_cells, y1)):
                for x in range(max(0, x0), min(w_cells, x1)):
                    e2_grid[y][x] = 0
    # Clamp to plot bounds to prevent road from going outside the plot!
    min_gx = int((0 - min_x) / RES)
    max_gx = int((sw - min_x) / RES)
    min_gy = int((0 - min_y) / RES)
    max_gy = int((sl - min_y) / RES)
    for y in range(h_cells):
        for x in range(w_cells):
            if x < min_gx or x > max_gx or y < min_gy or y > max_gy:
                e2_grid[y][x] = 0
                    
    # 4. Contour Tracing (Flood fill from outside)
    visited = set()
    # To avoid recursion limit, use a stack
    stack = [(0, 0)]
    visited.add((0, 0))
    while stack:
        cx, cy = stack.pop()
        for nx, ny in [(cx+1,cy), (cx-1,cy), (cx,cy+1), (cx,cy-1)]:
            if 0 <= nx < w_cells and 0 <= ny < h_cells:
                if e2_grid[ny][nx] == 0 and (nx, ny) not in visited:
                    visited.add((nx, ny))
                    stack.append((nx, ny))
                    
    edges = set()
    def is_outside(cx, cy):
        if cx < 0 or cx >= w_cells or cy < 0 or cy >= h_cells: return True
        return (cx, cy) in visited

    for y in range(h_cells):
        for x in range(w_cells):
            if not is_outside(x, y):
                if is_outside(x, y-1): edges.add(((x, y), (x+1, y)))
                if is_outside(x, y+1): edges.add(((x, y+1), (x+1, y+1)))
                if is_outside(x-1, y): edges.add(((x, y), (x, y+1)))
                if is_outside(x+1, y): edges.add(((x+1, y), (x+1, y+1)))
                
    real_edges = []
    for ((x1, y1), (x2, y2)) in edges:
        rx1, ry1 = min_x + x1*RES, min_y + y1*RES
        rx2, ry2 = min_x + x2*RES, min_y + y2*RES
        real_edges.append(((rx1, ry1), (rx2, ry2)))
        
    merged = []
    h_edges = [(min(e[0][0],e[1][0]), max(e[0][0],e[1][0]), e[0][1]) for e in real_edges if abs(e[0][1]-e[1][1]) < TOL]
    h_edges.sort(key=lambda x: (x[2], x[0]))
    if h_edges:
        cur_x0, cur_x1, cur_y = h_edges[0]
        for x0, x1, y in h_edges[1:]:
            if abs(y - cur_y) < TOL and x0 <= cur_x1 + TOL:
                cur_x1 = max(cur_x1, x1)
            else:
                merged.append(((cur_x0, cur_y), (cur_x1, cur_y)))
                cur_x0, cur_x1, cur_y = x0, x1, y
        merged.append(((cur_x0, cur_y), (cur_x1, cur_y)))
        
    v_edges = [(min(e[0][1],e[1][1]), max(e[0][1],e[1][1]), e[0][0]) for e in real_edges if abs(e[0][0]-e[1][0]) < TOL]
    v_edges.sort(key=lambda y: (y[2], y[0]))
    if v_edges:
        cur_y0, cur_y1, cur_x = v_edges[0]
        for y0, y1, x in v_edges[1:]:
            if abs(x - cur_x) < TOL and y0 <= cur_y1 + TOL:
                cur_y1 = max(cur_y1, y1)
            else:
                merged.append(((cur_x, cur_y0), (cur_x, cur_y1)))
                cur_y0, cur_y1, cur_x = y0, y1, x
        merged.append(((cur_x, cur_y0), (cur_x, cur_y1)))
        
    return merged, {"N":[], "S":[], "E":[], "W":[]}


def build_perimeter_road(sw, sl, cl_dist=PERIMETER_CL_DIST):
    """Closed polyline of perimeter fire road centerline."""
    d = cl_dist
    return [(d,d),(sw-d,d),(sw-d,sl-d),(d,sl-d),(d,d)]


# ── Rack — Step A: buffer rectangles per "need rack" block ───────────────
def rack_buffer_rect(block, offset):  # → §3.6.A
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


def compute_rack_buffers(blocks):  # → §3.6.A
    """Step A — per-block buffer rectangles for the 6 offsets a rack block uses.

    Returns {block_name: {offset_key: rect}} for every block.
    Each rect's outline is the buffer line at that offset."""
    return {
        b["name"]: {
            key: rack_buffer_rect(b, off)
            for key, off in RACK_BLOCK_OFFSETS.items()
        }
        for b in blocks
    }


def build_rack_spines(rack_buffers, blocks, sw, sl, ring_road=None, gate_spur=None, ring_spur=None):  # → §3.6.B (B-1..B-4)
    """Phase 06 Steps B-1 to B-4 — build PB-CT spine and candidates.

    Returns:
        spine_centerlines: List of lines (each a list of 2 points).
        candidate_points: List of (x, y) points from RAW and Demi.
        active_cases: Dict of which case was randomly selected for each block.
    """
    global _last_debug
    
    raw_cx, raw_cy = 0, 0
    pb_cx, pb_cy = 0, 0
    ct_cx, ct_cy = 0, 0
    for b in blocks:
        if b["name"] == "RAW Water Tank":
            raw_cx, raw_cy = b["x"] + b["width"]/2, b["y"] + b["height"]/2
        elif b["name"] == "Power Block":
            pb_cx, pb_cy = b["x"] + b["width"]/2, b["y"] + b["height"]/2
        elif b["name"] == "Cooling Tower":
            ct_cx, ct_cy = b["x"] + b["width"]/2, b["y"] + b["height"]/2

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

    def choose_case(name, rect_c1, rect_c2, cx, cy):
        # selected side of Case 2
        side_c2 = get_spine_side(rect_c2, cx, cy)
        p1, p2 = side_c2[0], side_c2[1]
        
        is_outside = False
        dist = 0.0
        if abs(p1[0] - p2[0]) < 0.1: # Vertical side
            dist = min(p1[0], sw - p1[0])
            if p1[0] < 0 or p1[0] > sw or min(p1[1], p2[1]) < 0 or max(p1[1], p2[1]) > sl:
                is_outside = True
        else: # Horizontal side
            dist = min(p1[1], sl - p1[1])
            if p1[1] < 0 or p1[1] > sl or min(p1[0], p2[0]) < 0 or max(p1[0], p2[0]) > sw:
                is_outside = True
                
        if dist < 10.0 or is_outside:
            return "case1_rack"
        else:
            return random.choice(["case1_rack", "case2_rack"])

    active_cases = {}
    for name in ("Power Block", "Cooling Tower", "RAW Water Tank", "Demi Water Tank", "WT/WWT"):
        if name in rack_buffers:
            if name in ("RAW Water Tank", "Demi Water Tank", "WT/WWT"):
                active_cases[name] = "case1_rack"
            elif name == "Power Block":
                active_cases[name] = choose_case("Power Block", rack_buffers["Power Block"]["case1_rack"], rack_buffers["Power Block"]["case2_rack"], pb_cx, pb_cy)
            elif name == "Cooling Tower":
                active_cases[name] = choose_case("Cooling Tower", rack_buffers["Cooling Tower"]["case1_rack"], rack_buffers["Cooling Tower"]["case2_rack"], ct_cx, ct_cy)

    if "Power Block" not in rack_buffers or "Cooling Tower" not in rack_buffers:
        return [], [], active_cases

    pb_rect = rack_buffers["Power Block"][active_cases["Power Block"]]
    ct_rect = rack_buffers["Cooling Tower"][active_cases["Cooling Tower"]]

    best_pb_side = get_spine_side(pb_rect, pb_cx, pb_cy)
    best_ct_side = get_spine_side(ct_rect, ct_cx, ct_cy)

    # Helper functions for B-1 midpoint splits and connections
    def split_segment(seg):
        p1, p2 = seg
        mid = ((p1[0]+p2[0])/2, (p1[1]+p2[1])/2)
        return [p1, mid], [mid, p2]

    def dist_sq(seg1, seg2):
        m1 = ((seg1[0][0]+seg1[1][0])/2, (seg1[0][1]+seg1[1][1])/2)
        m2 = ((seg2[0][0]+seg2[1][0])/2, (seg2[0][1]+seg2[1][1])/2)
        return (m1[0]-m2[0])**2 + (m1[1]-m2[1])**2

    def segments_overlap(s1, s2):
        p1a, p1b = s1
        p2a, p2b = s2
        s1_horiz = abs(p1a[1] - p1b[1]) < 0.1
        s2_horiz = abs(p2a[1] - p2b[1]) < 0.1
        if s1_horiz and s2_horiz:
            s1_x0, s1_x1 = min(p1a[0], p1b[0]), max(p1a[0], p1b[0])
            s2_x0, s2_x1 = min(p2a[0], p2b[0]), max(p2a[0], p2b[0])
            overlap = min(s1_x1, s2_x1) - max(s1_x0, s2_x0)
            return overlap > 0.1
        elif not s1_horiz and not s2_horiz:
            s1_y0, s1_y1 = min(p1a[1], p1b[1]), max(p1a[1], p1b[1])
            s2_y0, s2_y1 = min(p2a[1], p2b[1]), max(p2a[1], p2b[1])
            overlap = min(s1_y1, s2_y1) - max(s1_y0, s2_y0)
            return overlap > 0.1
        return False

    def closest_perp_line(seg, target_seg):
        p1, p2 = seg
        t1, t2 = target_seg
        is_horiz = abs(p1[1] - p2[1]) < 0.1
        if is_horiz:
            y_seg = p1[1]
            y_tgt = t1[1]
            seg_x0, seg_x1 = min(p1[0], p2[0]), max(p1[0], p2[0])
            tgt_x0, tgt_x1 = min(t1[0], t2[0]), max(t1[0], t2[0])
            ox0 = max(seg_x0, tgt_x0)
            ox1 = min(seg_x1, tgt_x1)
            if ox1 >= ox0:
                x_mid = (ox0 + ox1) / 2
                return [(x_mid, y_seg), (x_mid, y_tgt)]
            else:
                if seg_x1 < tgt_x0:
                    return [(seg_x1, y_seg), (tgt_x0, y_tgt)]
                else:
                    return [(seg_x0, y_seg), (tgt_x1, y_tgt)]
        else:
            x_seg = p1[0]
            x_tgt = t1[0]
            seg_y0, seg_y1 = min(p1[1], p2[1]), max(p1[1], p2[1])
            tgt_y0, tgt_y1 = min(t1[1], t2[1]), max(t1[1], t2[1])
            oy0 = max(seg_y0, tgt_y0)
            oy1 = min(seg_y1, tgt_y1)
            if oy1 >= oy0:
                y_mid = (oy0 + oy1) / 2
                return [(x_seg, y_mid), (x_tgt, y_mid)]
            else:
                if seg_y1 < tgt_y0:
                    return [(x_seg, seg_y1), (x_tgt, tgt_y0)]
                else:
                    return [(x_seg, seg_y0), (x_tgt, tgt_y1)]

    pb_halves = split_segment(best_pb_side)
    ct_halves = split_segment(best_ct_side)

    best_pair = None
    min_d = float('inf')
    for pb_h in pb_halves:
        for ct_h in ct_halves:
            d = dist_sq(pb_h, ct_h)
            if d < min_d:
                min_d = d
                best_pair = (pb_h, ct_h)

    best_pb_half, best_ct_half = best_pair

    # Under overlap exception:
    is_overlap = segments_overlap(best_pb_side, best_ct_side)
    pb_case = active_cases["Power Block"]
    ct_case = active_cases["Cooling Tower"]

    p1a, p1b = best_pb_side
    p2a, p2b = best_ct_side
    is_pb_horiz = abs(p1a[1] - p1b[1]) < 0.1
    is_ct_horiz = abs(p2a[1] - p2b[1]) < 0.1

    spine_creation_debug = {
        "pb_case": pb_case,
        "ct_case": ct_case,
        "is_horizontal": is_pb_horiz and is_ct_horiz,
        "is_vertical": not is_pb_horiz and not is_ct_horiz,
        "overlap": is_overlap,
        "spine_centerlines": None,
        "perp_line": None,
        "perp_to_pb_center": None,
        "main_rack": None
    }

    spine_centerlines = [best_pb_half, best_ct_half]

    if is_overlap and pb_case == "case1_rack" and ct_case == "case2_rack":
        perp_line = closest_perp_line(best_pb_half, best_ct_side)
        spine_centerlines.append(perp_line)
        spine_creation_debug["perp_line"] = perp_line
    elif is_overlap and pb_case == "case2_rack" and ct_case == "case1_rack":
        perp_line = closest_perp_line(best_ct_half, best_pb_side)
        spine_centerlines.append(perp_line)
        spine_creation_debug["perp_line"] = perp_line

        p1, p2 = best_ct_half
        is_horiz = abs(p1[1] - p2[1]) < 0.1
        if is_horiz:
            perp_to_pb_center = [(pb_cx, p1[1]), (pb_cx, pb_cy)]
        else:
            perp_to_pb_center = [(p1[0], pb_cy), (pb_cx, pb_cy)]
        spine_centerlines.append(perp_to_pb_center)
        spine_creation_debug["perp_to_pb_center"] = perp_to_pb_center
    else:
        p1, p2 = best_pb_half
        is_horiz = abs(p1[1] - p2[1]) < 0.1
        if is_horiz:
            perp_pt = (pb_cx, p1[1])
        else:
            perp_pt = (p1[0], pb_cy)
        main_rack = [(pb_cx, pb_cy), perp_pt]
        spine_centerlines.append(main_rack)
        spine_creation_debug["main_rack"] = main_rack

    # 7. Connect PB and CT centerlines (Step B-1 rule 7)
    if not is_overlap:
        grid_b1 = Grid(sw, sl, cell_size=CELL_SIZE)
        for b in blocks:
            grid_b1.mark_building(b, inflate_m=0)

        grid_b2 = Grid(sw, sl, cell_size=CELL_SIZE)
        for b in blocks:
            if b["name"] != "Power Block":
                grid_b2.mark_building(b, inflate_m=0)
            
        def get_seg_cells(seg):
            cells = []
            c1 = grid_b1.world_to_cell(*seg[0])
            c2 = grid_b1.world_to_cell(*seg[1])
            if c1[0] == c2[0]:
                for y in range(min(c1[1], c2[1]), max(c1[1], c2[1]) + 1):
                    if 0 <= c1[0] < grid_b1.ncols and 0 <= y < grid_b1.nrows:
                        cells.append((c1[0], y))
            elif c1[1] == c2[1]:
                for x in range(min(c1[0], c2[0]), max(c1[0], c2[0]) + 1):
                    if 0 <= x < grid_b1.ncols and 0 <= c1[1] < grid_b1.nrows:
                        cells.append((x, c1[1]))
            return cells
            
        road_segs = []
        if ring_road:
            for i in range(len(ring_road) - 1):
                road_segs.append((ring_road[i], ring_road[i+1]))
            road_segs.append((ring_road[-1], ring_road[0]))
        if gate_spur:
            for i in range(len(gate_spur) - 1):
                road_segs.append((gate_spur[i], gate_spur[i+1]))
        if ring_spur:
            for i in range(len(ring_spur) - 1):
                road_segs.append((ring_spur[i], ring_spur[i+1]))
                
        horiz_roads = []
        vert_roads = []
        for p1, p2 in road_segs:
            c1 = grid_b1.world_to_cell(*p1)
            c2 = grid_b1.world_to_cell(*p2)
            if c1[1] == c2[1]:
                horiz_roads.append((p1[1], min(p1[0], p2[0]), max(p1[0], p2[0])))
            elif c1[0] == c2[0]:
                vert_roads.append((p1[0], min(p1[1], p2[1]), max(p1[1], p2[1])))
                
        exempt_horiz = []
        exempt_vert = []
        for b in blocks:
            b_name = b["name"]
            if b_name in rack_buffers:
                if b_name in active_cases:
                    cases = [active_cases[b_name]]
                else:
                    cases = list(rack_buffers[b_name].keys())
                for case in cases:
                    rx, ry, rw, rh = rack_buffers[b_name][case]
                    if b_name == "Power Block":
                        exempt_horiz.append((ry, rx - PB_RING_OFFSET, rx + rw + PB_RING_OFFSET))
                        exempt_horiz.append((ry+rh, rx - PB_RING_OFFSET, rx + rw + PB_RING_OFFSET))
                        exempt_vert.append((rx, ry - PB_RING_OFFSET, ry + rh + PB_RING_OFFSET))
                        exempt_vert.append((rx+rw, ry - PB_RING_OFFSET, ry + rh + PB_RING_OFFSET))
                    else:
                        exempt_horiz.append((ry, rx, rx+rw))
                        exempt_horiz.append((ry+rh, rx, rx+rw))
                        exempt_vert.append((rx, ry, ry+rh))
                        exempt_vert.append((rx+rw, ry, ry+rh))

        def forbid_move_hook(from_cell, di, dj):
            to_cell = (from_cell[0] + di, from_cell[1] + dj)
            p1 = (from_cell[0] * CELL_SIZE, from_cell[1] * CELL_SIZE)
            p2 = (to_cell[0] * CELL_SIZE, to_cell[1] * CELL_SIZE)
            
            if dj == 0:
                for ey, ex0, ex1 in exempt_horiz:
                    if abs(p1[1] - ey) < 0.1:
                        if ex0 - 0.1 <= min(p1[0], p2[0]) and max(p1[0], p2[0]) <= ex1 + 0.1:
                            return False
                move_x_min, move_x_max = min(p1[0], p2[0]), max(p1[0], p2[0])
                for ry, rx0, rx1 in horiz_roads:
                    if min(move_x_max, rx1) >= max(move_x_min, rx0) - 0.1:
                        if abs(p1[1] - ry) < 9.0 - 0.1:
                            return True
            elif di == 0:
                for ex, ey0, ey1 in exempt_vert:
                    if abs(p1[0] - ex) < 0.1:
                        if ey0 - 0.1 <= min(p1[1], p2[1]) and max(p1[1], p2[1]) <= ey1 + 0.1:
                            return False
                move_y_min, move_y_max = min(p1[1], p2[1]), max(p1[1], p2[1])
                for rx, ry0, ry1 in vert_roads:
                    if min(move_y_max, ry1) >= max(move_y_min, ry0) - 0.1:
                        if abs(p1[0] - rx) < 9.0 - 0.1:
                            return True
            return False

        # Search 1: Spine-to-Spine (Power Block footprint is BLOCKED)
        start_cells_1 = get_seg_cells(best_pb_half)
        goal_cells_1 = set(get_seg_cells(best_ct_half))
        for c in start_cells_1:
            grid_b1.blocked[c] = False
        for c in goal_cells_1:
            grid_b1.blocked[c] = False
            
        path_1 = astar(
            grid_b1,
            start_cells_1,
            goal_cells_1,
            turn_penalty=10.0,
            width_cells=0,
            allow_diagonal=False,
            forbid_move=forbid_move_hook
        )
        dist_1 = (len(path_1) - 1) * CELL_SIZE if path_1 else float('inf')

        # Search 2: Main Rack-to-Spine (Power Block footprint is NOT BLOCKED)
        start_cells_2 = get_seg_cells(main_rack)
        goal_cells_2 = set(get_seg_cells(best_ct_half))
        for c in start_cells_2:
            grid_b2.blocked[c] = False
        for c in goal_cells_2:
            grid_b2.blocked[c] = False
            
        path_2 = astar(
            grid_b2,
            start_cells_2,
            goal_cells_2,
            turn_penalty=10.0,
            width_cells=0,
            allow_diagonal=False,
            forbid_move=forbid_move_hook
        )
        dist_2 = (len(path_2) - 1) * CELL_SIZE if path_2 else float('inf')

        # Compare and pick the shorter connection path
        if dist_2 < dist_1:
            path = path_2
            grid_to_use = grid_b2
        else:
            path = path_1
            grid_to_use = grid_b1

        if path:
            valid_xs = set()
            valid_ys = set()
            for b in blocks:
                b_name = b["name"]
                if b_name in rack_buffers:
                    if b_name in active_cases:
                        cases = [active_cases[b_name]]
                    else:
                        cases = list(rack_buffers[b_name].keys())
                    for case in cases:
                        rx, ry, rw, rh = rack_buffers[b_name][case]
                        valid_xs.update([rx, rx+rw])
                        valid_ys.update([ry, ry+rh])
                        
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

            path_pts = [snap_pt(*grid_to_use.cell_to_world(*c)) for c in path]
            simplified = [path_pts[0]]
            for i in range(1, len(path_pts)-1):
                p0, p1, p2 = simplified[-1], path_pts[i], path_pts[i+1]
                if not (p0[0] == p1[0] == p2[0] or p0[1] == p1[1] == p2[1]):
                    simplified.append(p1)
            simplified.append(path_pts[-1])
            
            for i in range(len(simplified)-1):
                seg = [simplified[i], simplified[i+1]]
                spine_centerlines.append(seg)

    spine_creation_debug["spine_centerlines"] = spine_centerlines
    _last_debug["spine_creation"] = spine_creation_debug

    pb_spine_mid = ((best_pb_half[0][0] + best_pb_half[1][0])/2, (best_pb_half[0][1] + best_pb_half[1][1])/2)
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


def build_gate_spur(site_w, site_l, gate_pt):  # → §3.4.B (simple fallback; main logic is inline in generate_sketch)
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


# ── Placement debug state (populated by generate_sketch, readable from dashboard) ──
_last_debug: dict = {}

_FIXED_BLOCKS = ("Gate House", "GIS", "RAW Water Tank")


def _spur_exclusion_rect(line, buffer=ROAD_BUFFER):  # → §3.4.B · §3.4.D (keeps floated blocks ≥8m from spur CLs)
    """List of axis-aligned bounding boxes for each segment of a spur line, inflated by `buffer`.
    Used as virtual exclusion zones during floated-block placement."""
    if not line or len(line) < 2:
        return []
    rects = []
    for i in range(len(line)-1):
        p1, p2 = line[i], line[i+1]
        x0, x1 = min(p1[0], p2[0]) - buffer, max(p1[0], p2[0]) + buffer
        y0, y1 = min(p1[1], p2[1]) - buffer, max(p1[1], p2[1]) + buffer
        rects.append((x0, y0, x1 - x0, y1 - y0))
    return rects


def _seg_aabb_intersect(p1, p2, rx, ry, rw, rh):  # → §3.4.D (used by build_ring_spur to avoid fixed blocks)
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

def generate_group_a_access(computed_buffers, placed, site_w, site_l, gate_cx, gate_cy):  # → §3.7.C · §3.8.B
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
    
    for name, buffer_bounds in computed_buffers.items():
        if name not in GROUP_A_BLOCKS:
            continue
            
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

def build_ring_spur(site_w, site_l, ring_road, blocks, gate_pt):  # → §3.4.D
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
        # Snap spur start to corner or center of ring road side closest to gate
        x_center = (rxmin + rxmax) / 2
        snap_candidates = sorted([rxmin, x_center, rxmax], key=lambda x: abs(x - gx))
        target = max(x_min, min(x_max, snap_candidates[0]))
        for dx in [0] + SHIFTS:
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
    # Snap spur start to corner or center of ring road side closest to gate
    y_center = (rymin + rymax) / 2
    snap_candidates = sorted([rymin, y_center, rymax], key=lambda y: abs(y - gy))
    target = max(y_min, min(y_max, snap_candidates[0]))
    for dy in [0] + SHIFTS:
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




# ── Main generator ────────────────────────────────────────────────────────
def cleanup_parallel_segments(segs, sw, sl, computed_buffers, ref_segs=None, tol=17.0, gdz=None, pb_cx=0):  # → §3.7.D (Priority 1..3)
    if ref_segs is None:
        ref_segs = []
        
    ref_horiz = []
    ref_vert = []
    for (x1, y1), (x2, y2) in ref_segs:
        if abs(y1 - y2) < 0.1:
            ref_horiz.append([(min(x1, x2), y1), (max(x1, x2), y2)])
        elif abs(x1 - x2) < 0.1:
            ref_vert.append([(x1, min(y1, y2)), (x2, max(y1, y2))])

    horiz = []
    vert = []
    for (x1, y1), (x2, y2) in segs:
        if abs(y1 - y2) < 0.1:
            horiz.append([(min(x1, x2), y1), (max(x1, x2), y2)])
        elif abs(x1 - x2) < 0.1:
            vert.append([(x1, min(y1, y2)), (x2, max(y1, y2))])
            
    def get_outward_dir(l, is_horiz):
        val = l[0][1] if is_horiz else l[0][0]
        for name, b in computed_buffers.items():
            if is_horiz:
                if abs(val - min(sl, b[3])) < 0.1: return 1  # Top
                if abs(val - max(0, b[1])) < 0.1: return -1  # Bottom
            else:
                if abs(val - min(sw, b[2])) < 0.1: return 1  # Right
                if abs(val - max(0, b[0])) < 0.1: return -1  # Left
        return 1 if val >= (sl/2 if is_horiz else sw/2) else -1

    # Priority 1 & 2: Snap to PB network and filter out from Priority 3
    def snap_to_ref(lines, refs, is_horiz):
        kept_for_p3 = []
        snapped_final = []
        
        for l in lines:
            snapped = False
            outward = get_outward_dir(l, is_horiz)
            for r in refs:
                # Exception: If reference line is in the Gate Death Zone, do not snap to it
                if gdz is not None:
                    gx, gy, gw, gh = gdz
                    rmid_x = (r[0][0] + r[1][0]) / 2
                    rmid_y = (r[0][1] + r[1][1]) / 2
                    if gx <= rmid_x <= gx + gw and gy <= rmid_y <= gy + gh:
                        continue
                        
                if is_horiz:
                    if 0 <= abs(l[0][1] - r[0][1]) <= tol:
                        # Ensure we only snap outward
                        if outward == 1 and r[0][1] < l[0][1]: continue
                        if outward == -1 and r[0][1] > l[0][1]: continue
                        
                        overlap = min(l[1][0], r[1][0]) - max(l[0][0], r[0][0])
                        if overlap > -0.1:
                            l = [(l[0][0], r[0][1]), (l[1][0], r[0][1])]
                            snapped = True
                            break
                else:
                    if 0 <= abs(l[0][0] - r[0][0]) <= tol:
                        # Ensure we only snap outward
                        if outward == 1 and r[0][0] < l[0][0]: continue
                        if outward == -1 and r[0][0] > l[0][0]: continue
                        
                        overlap = min(l[1][1], r[1][1]) - max(l[0][1], r[0][1])
                        if overlap > -0.1:
                            l = [(r[0][0], l[0][1]), (r[0][0], l[1][1])]
                            snapped = True
                            break
            if snapped:
                snapped_final.append(l)
            else:
                kept_for_p3.append(l)
        return kept_for_p3, snapped_final
        
    horiz, horiz_snapped = snap_to_ref(horiz, ref_horiz, True)
    vert, vert_snapped = snap_to_ref(vert, ref_vert, False)
            
    # Priority 3: Simplified sweep with Left/Right separation and Buffer Guard.
    def is_inside_buffer(p_min, p_max, val, is_horiz):
        for name, b in computed_buffers.items():
            bx_min, by_min, bx_max, by_max = b
            if is_horiz:
                if by_min + 0.1 < val < by_max - 0.1:
                    if min(p_max, bx_max) > max(p_min, bx_min) + 0.1:
                        return True
            else:
                if bx_min + 0.1 < val < bx_max - 0.1:
                    if min(p_max, by_max) > max(p_min, by_min) + 0.1:
                        return True
        return False

    # 1. Horizontal Sweep
    left_horiz = [l for l in horiz if (l[0][0] + l[1][0]) / 2 < pb_cx]
    right_horiz = [l for l in horiz if (l[0][0] + l[1][0]) / 2 >= pb_cx]
    
    def sweep_horizontal_group(group):
        group.sort(key=lambda l: l[0][1], reverse=True) # Sort by highest Y
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                l1, l2 = group[i], group[j]
                target_y = l1[0][1]
                if 0 <= target_y - l2[0][1] <= tol:
                    # Apply buffer guard check
                    if not is_inside_buffer(l2[0][0], l2[1][0], target_y, is_horiz=True):
                        group[j] = [(l2[0][0], target_y), (l2[1][0], target_y)]
                        
    sweep_horizontal_group(left_horiz)
    sweep_horizontal_group(right_horiz)
    horiz = left_horiz + right_horiz

    # 2. Vertical Sweep
    left_vert = [l for l in vert if l[0][0] < pb_cx]
    right_vert = [l for l in vert if l[0][0] >= pb_cx]
    
    def sweep_vertical_group(group):
        group.sort(key=lambda l: l[0][0]) # Sort by lowest X
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                l1, l2 = group[i], group[j]
                target_x = l1[0][0]
                if 0 <= l2[0][0] - target_x <= tol:
                    # Apply buffer guard check
                    if not is_inside_buffer(l2[0][1], l2[1][1], target_x, is_horiz=False):
                        group[j] = [(target_x, l2[0][1]), (target_x, l2[1][1])]
                        
    sweep_vertical_group(left_vert)
    sweep_vertical_group(right_vert)
    vert = left_vert + right_vert
        
    # Merge collinear overlapping again after sweeps
    h_merged = []
    for l in horiz:
        if not h_merged:
            h_merged.append(l)
            continue
        merged = False
        for i, r in enumerate(h_merged):
            if abs(l[0][1] - r[0][1]) < 0.1:
                overlap = min(l[1][0], r[1][0]) - max(l[0][0], r[0][0])
                if overlap > -0.1:
                    h_merged[i] = [(min(l[0][0], r[0][0]), l[0][1]), (max(l[1][0], r[1][0]), l[0][1])]
                    merged = True
                    break
        if not merged:
            h_merged.append(l)
            
    v_merged = []
    for l in vert:
        if not v_merged:
            v_merged.append(l)
            continue
        merged = False
        for i, r in enumerate(v_merged):
            if abs(l[0][0] - r[0][0]) < 0.1:
                overlap = min(l[1][1], r[1][1]) - max(l[0][1], r[0][1])
                if overlap > -0.1:
                    v_merged[i] = [(l[0][0], min(l[0][1], r[0][1])), (l[0][0], max(l[1][1], r[1][1]))]
                    merged = True
                    break
        if not merged:
            v_merged.append(l)
            
    # Add back the lines that snapped to the PB network
    h_merged.extend(horiz_snapped)
    v_merged.extend(vert_snapped)
            
    return h_merged + v_merged

def generate_sketch(  # → §3.1 Master Placement Sequence
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
    global _last_debug
    sw, sl = site_w, site_l
    gate_pt = compute_gate(sw, sl, gate_side, gate_ratio)

    # Reset debug state for this run
    _last_debug = {
        "site": (sw, sl),
        "max_pool": max_pool,
        "total_attempts": 0,
        "fail_counts": {},      # {block_name: # attempts where it caused failure}
        "last_placed": {},      # {block_name: (x,y,w,h)} from the deepest attempt
        "failed_at": None,      # block or section that failed last
        "failed_section": None, # §-ref for the failure
        "boundary_tol_used": None,  # which pass succeeded
    }

    # Three-pass placement strategy — each pass runs max_pool attempts.
    # Pass 1 (tol=-18): blocks must sit ≥18m inside every boundary (strictest).
    # Pass 2 (tol=  0): blocks must be fully inside the plot, no margin required.
    # Pass 3 (tol= 10): blocks may spill up to 10m outside the plot boundary.
    # Implemented as one flat loop: attempts 0..max_pool-1 = pass 1, next block
    # = pass 2, etc. On success we return; on max_pool failures we fall into the
    # next pass's tolerance automatically.
    _PASS_TOLS = [
        (-18, "pass 1 — strict (18m inner margin)"),
        (  0, "pass 2 — inside plot (0m tolerance)"),
        ( BOUNDARY_TOLERANCE, f"pass 3 — relaxed ({BOUNDARY_TOLERANCE}m spillage)"),
    ]

    for _attempt in range(max_pool * len(_PASS_TOLS)):
        _pass_tol, _pass_label = _PASS_TOLS[_attempt // max_pool]
        _last_debug["total_attempts"] += 1
        _last_debug["boundary_pass_label"] = _pass_label

        placed = {}   # name → (x, y, w, h)

        # 1. Fixed anchors  [→ §3.2] — jitter ±5% of site dim around fixed position (GIS is fully fixed, no jitter)
        for name, edge, ratio, off in [
            ("Gate House",     gh_edge,    gh_ratio,    gh_offset),
            ("GIS",            gis_edge,   gis_ratio,   gis_offset),
            ("RAW Water Tank", water_edge, water_ratio, water_offset),
        ]:
            j = 0.0 if name == "GIS" else 0.05
            x, y, w, h = place_anchor(sw, sl, name, edge, ratio, off, jitter=j)
            placed[name] = (x, y, w, h)

        # 2. Power Block  [→ §3.3]
        # Tight-site logic: if vertical clearance on each side < 60m,
        # shift PB by ±20% of site length instead of ±5% jitter.
        pw, ph = BLOCK_FOOTPRINTS["Power Block"]
        road_w = 8
        # PB placement uses its ROAD BUFFER geometry, not the bare footprint:
        # the block + 14m rack road buffer (= ring road corridor) must stay inside
        # the plot, so PB is effectively treated as (150+2*14) wide when clamping.
        pb_buf = ROAD_W_RACK_OFFSET   # 14m — PB rack-side road buffer
        tight_site = (sl - ph - road_w * 2) / 2 < 60

        # PB origin clamp bounds. Default: buffered rect stays BOUNDARY_TOLERANCE
        # inside every edge (face inset = 10 + 14 = 24m).
        m = BOUNDARY_TOLERANCE + pb_buf
        pb_x_bounds = [m, sw - pw - m]
        pb_y_bounds = [m, sl - ph - m]
        # Gate-side override: PB's ring road stops at the Gate House ROAD BUFFER
        # edge that is (a) PARALLEL to the plot's gate side and (b) CLOSEST to the
        # plot center. The ring road centerline (14m) rests on that buffer edge.
        cx_plot, cy_plot = sw / 2, sl / 2
        ghx, ghy, ghw, ghh = placed["Gate House"]
        gh_buf = ROAD_BUFFER   # ROAD_BUFFER — Gate House road buffer
        b_bottom = ghy - gh_buf
        b_top    = ghy + ghh + gh_buf
        b_left   = ghx - gh_buf
        b_right  = ghx + ghw + gh_buf
        if gate_side in ("N", "S"):
            # gate side is horizontal → parallel buffer edges are bottom & top;
            # pick the one whose y is closest to plot center.
            if abs(b_bottom - cy_plot) <= abs(b_top - cy_plot):
                gh_near_edge = "buf_bottom"
                pb_y_bounds[1] = b_bottom - ph - PB_RING_OFFSET   # ring top ≤ buf bottom
            else:
                gh_near_edge = "buf_top"
                pb_y_bounds[0] = b_top + PB_RING_OFFSET           # ring bottom ≥ buf top
        else:
            # gate side is vertical → parallel buffer edges are left & right;
            # pick the one whose x is closest to plot center.
            if abs(b_left - cx_plot) <= abs(b_right - cx_plot):
                gh_near_edge = "buf_left"
                pb_x_bounds[1] = b_left - pw - PB_RING_OFFSET      # ring right ≤ buf left
            else:
                gh_near_edge = "buf_right"
                pb_x_bounds[0] = b_right + PB_RING_OFFSET          # ring left ≥ buf right

        def _pb_sample():
            # Asymmetric wind-direction-aware random offsets from center (PB-01)
            if wind_dir == "East":
                dx = random.uniform(-sw * 0.05, sw * 0.35)
                if tight_site:
                    dy = random.choice([-sl * 0.20, sl * 0.20])
                else:
                    dy = random.uniform(-sl * 0.20, sl * 0.20)
            elif wind_dir == "West":
                dx = random.uniform(-sw * 0.35, sw * 0.05)
                if tight_site:
                    dy = random.choice([-sl * 0.20, sl * 0.20])
                else:
                    dy = random.uniform(-sl * 0.20, sl * 0.20)
            elif wind_dir == "North":
                dx = random.uniform(-sw * 0.20, sw * 0.20)
                if tight_site:
                    dy = random.choice([-sl * 0.05, sl * 0.35])
                else:
                    dy = random.uniform(-sl * 0.05, sl * 0.35)
            elif wind_dir == "South":
                dx = random.uniform(-sw * 0.20, sw * 0.20)
                if tight_site:
                    dy = random.choice([-sl * 0.35, sl * 0.05])
                else:
                    dy = random.uniform(-sl * 0.35, sl * 0.05)
            else:
                dx = random.uniform(-sw * 0.20, sw * 0.20)
                if tight_site:
                    dy = random.choice([-sl * 0.20, sl * 0.20])
                else:
                    dy = random.uniform(-sl * 0.05, sl * 0.05)

            cx = (sw - pw) / 2 + dx
            cy = (sl - ph) / 2 + dy
            return (max(pb_x_bounds[0], min(cx, pb_x_bounds[1])),
                    max(pb_y_bounds[0], min(cy, pb_y_bounds[1])))
        pb_result = _try_place(sw, sl, "Power Block", placed, _pb_sample, max_attempts=100,
                               buffer=pb_buf, x_bounds=tuple(pb_x_bounds), y_bounds=tuple(pb_y_bounds))
        if pb_result is None:
            _last_debug["failed_at"] = "Power Block"
            _last_debug["failed_section"] = "§3.3 Power Block"
            if "fail_counts" not in _last_debug:
                _last_debug["fail_counts"] = {}
            _last_debug["fail_counts"]["Power Block"] = _last_debug["fail_counts"].get("Power Block", 0) + 1
            # Record which blocks DID place in this attempt
            _last_debug["last_placed"] = {n: v for n, v in placed.items() if not n.startswith("_")}
            continue
        pb_x, pb_y, pb_w, pb_h = pb_result
        placed["Power Block"] = pb_result
        pb_cx, pb_cy = pb_x + pb_w/2, pb_y + pb_h/2

        # Debug: gate-side ring-road vs Gate-House-inner-edge check
        _last_debug["pb_gate_check"] = {
            "gate_side": gate_side, "gh_edge": gh_edge,
            "gh_near_edge (closest to center)": gh_near_edge,
            "gh": (round(ghx,1), round(ghy,1), round(ghw,1), round(ghh,1)),
            "pb_y": round(pb_y,1), "pb_x": round(pb_x,1),
            "pb_y_bounds": [round(pb_y_bounds[0],1), round(pb_y_bounds[1],1)],
            "pb_x_bounds": [round(pb_x_bounds[0],1), round(pb_x_bounds[1],1)],
            "ring_top": round(pb_y + pb_h + PB_RING_OFFSET, 1),
            "ring_bottom": round(pb_y - PB_RING_OFFSET, 1),
            "ring_left": round(pb_x - PB_RING_OFFSET, 1),
            "ring_right": round(pb_x + pb_w + PB_RING_OFFSET, 1),
            "buf_bottom": round(b_bottom, 1),
            "buf_top": round(b_top, 1),
            "buf_left": round(b_left, 1),
            "buf_right": round(b_right, 1),
        }

        # 3. PB Ring Road geometry + lock the road corridor for floated block placement  [→ §3.4.A]
        ring_road = build_pb_ring_road(pb_x, pb_y, pb_w, pb_h)

        # Virtual exclusion zone to keep floated blocks exactly 8m away from the ring road centerline:
        # PB_RING_OFFSET = 14m (centerline from face) + Road Buffer = 8m (keep block 8m from centerline) = 22m total from PB face
        ring_outer = PB_RING_OFFSET + ROAD_BUFFER   # PB ring CL + road buffer
        placed["_pb_ring_zone"] = (
            pb_x - ring_outer,
            pb_y - ring_outer,
            pb_w + 2 * ring_outer,
            pb_h + 2 * ring_outer,
        )

        # 3b. Gate Spur + Ring Spur — built before floated blocks so  [→ §3.4.B · §3.4.D]
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
            # Calculate Gate Death Zone (only if gate and gate house are on the same edge)  [→ §3.4.C]
            if gate_side == gh_edge:
                gdz_x_min = min(bb_mid[0], gate_pt[0])
                gdz_x_max = max(bb_mid[0], gate_pt[0])
                gdz_y_min = min(bb_mid[1], gate_pt[1])
                gdz_y_max = max(bb_mid[1], gate_pt[1])
                # Ensure it's a valid rectangle even if aligned
                if gdz_x_max - gdz_x_min < 1:
                    gdz_x_min -= 1; gdz_x_max += 1
                if gdz_y_max - gdz_y_min < 1:
                    gdz_y_min -= 1; gdz_y_max += 1
                gate_death_zone = (gdz_x_min, gdz_y_min, gdz_x_max - gdz_x_min, gdz_y_max - gdz_y_min)
                placed["_gate_death_zone"] = gate_death_zone
            else:
                gate_death_zone = None

            # exit_helper sits on the Gate House buffer corner shared by two edges:
            #   - the boom edge (the bb_edge side, carrying the boom barrier)
            #   - the "exit_helper_line": the perpendicular buffer edge that holds
            #     exit_helper but NOT the boom.
            # exit_helper_opp = the OTHER end of exit_helper_line (away from boom).
            # We enter the ring spur near exit_helper_opp, run along exit_helper_line
            # to exit_helper, then cross the boom once via gate_spur — so the spur
            # approaches from the non-boom side and never loops the long way round.
            if bb_edge in ("N", "S"):
                opp_perp = (gh_y - 8) if bb_edge == "N" else (gh_y + gh_h + 8)
                exit_helper_opp = (exit_helper[0], opp_perp)
            else:
                opp_perp = (gh_x - 8) if bb_edge == "E" else (gh_x + gh_w + 8)
                exit_helper_opp = (opp_perp, exit_helper[1])

            # Ring start point = ring-road corner closest to exit_helper (4 corners, no midpoint)
            rxs = [p[0] for p in ring_road]; rys = [p[1] for p in ring_road]
            rxmin, rxmax = min(rxs), max(rxs)
            rymin, rymax = min(rys), max(rys)
            ring_corners = [(rxmin, rymin), (rxmax, rymin), (rxmax, rymax), (rxmin, rymax)]
            ehx, ehy = exit_helper

            # 1. Try closest corner first
            closest_corner = min(ring_corners, key=lambda c: (c[0]-ehx)**2 + (c[1]-ehy)**2)
            sx, sy = closest_corner

            # Check if this corner causes a 180-degree U-turn (backtracking) at exit_helper.
            # The direction of the final Ring Spur segment (from turn_pt to exit_helper) must align
            # with the direction of the first Gate Spur segment (from exit_helper to bb_mid).
            # - For N/S boom edges, the segments are horizontal:
            #   Ring Spur: (sx, ehy) -> (ehx, ehy)  (direction: ehx - sx)
            #   Gate Spur: (ehx, ehy) -> (bb_mid[0], ehy)  (direction: bb_mid[0] - ehx)
            #   To avoid a U-turn, (ehx - sx) * (bb_mid[0] - ehx) must be >= 0.
            # - For E/W boom edges, the segments are vertical:
            #   Ring Spur: (ehx, sy) -> (ehx, ehy)  (direction: ehy - sy)
            #   Gate Spur: (ehx, ehy) -> (ehx, bb_mid[1])  (direction: bb_mid[1] - ehy)
            #   To avoid a U-turn, (ehy - sy) * (bb_mid[1] - ehy) must be >= 0.
            if bb_edge in ("N", "S"):
                is_valid = (ehx - sx) * (bb_mid[0] - ehx) >= 0
            else:
                is_valid = (ehy - sy) * (bb_mid[1] - ehy) >= 0

            if is_valid:
                spur_start = closest_corner
                # Ring spur L-route (Option A): project spur_start onto exit_line
                if bb_edge in ("N", "S"):
                    turn_pt = (sx, ehy)
                else:
                    turn_pt = (ehx, sy)
                ring_spur = [spur_start, turn_pt, exit_helper]
            else:
                # If closest corner is invalid (causes U-turn), fall back to projection of exit_helper onto Ring Road edge.
                if bb_edge in ("N", "S"):
                    sy_proj = rymax if abs(ehy - rymax) < abs(ehy - rymin) else rymin
                    spur_start = (ehx, sy_proj)
                else:
                    sx_proj = rxmax if abs(ehx - rxmax) < abs(ehx - rxmin) else rxmin
                    spur_start = (sx_proj, ehy)
                # Straight 1-segment spur directly from the projected point on the Ring Road edge
                ring_spur = [spur_start, exit_helper]

            # gate_spur — KEEP original: cross the boom at bb_mid, route to gate.
            if bb_edge in ("N", "S"):
                gate_spur = [exit_helper, bb_mid, other_corner, (gate_pt[0], other_corner[1]), gate_pt]
            else:
                gate_spur = [exit_helper, bb_mid, other_corner, (other_corner[0], gate_pt[1]), gate_pt]
        else:
            gate_death_zone = None
            gate_spur = build_gate_spur(sw, sl, gate_pt)
            ring_spur = build_ring_spur(sw, sl, ring_road, fixed_blocks_so_far, gate_pt)
        for zone_name, line in (("_gate_spur_zone", gate_spur),
                                ("_ring_spur_zone", ring_spur)):
            rects = _spur_exclusion_rect(line, buffer=ROAD_BUFFER)
            for i, rect in enumerate(rects):
                placed[f"{zone_name}_{i}"] = rect

        # 4. Floated blocks — magnet placement with zone rules.  [→ §3.5]
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
            ("Flare",           flare_corner,     leeward_filter,  None),
            ("Cooling Tower",   (pb_cx, pb_cy),   leeward_filter,  "Power Block"),
            ("WT/WWT",          (pb_cx, pb_cy),   near_raw_filter, "Power Block"),
            ("Warehouse",       None,             None,            "Power Block"),
            ("Admin Building",  admin_anchor,     None,            "Power Block"),
            ("Demi Water Tank", (raw_cx, raw_cy), near_raw_filter, "RAW Water Tank"),
        ]

        ok = True
        for name, prefer, f_fn, m_target in floated_order:
            if name == "Flare":
                # Custom corner placement for Flare (no magnetization)
                w, h = BLOCK_FOOTPRINTS["Flare"]
                margin = -_pass_tol
                
                # Determine corner priority order based on wind direction (leeward corners first)
                if wind_dir == "East":
                    corner_priorities = [(0, 0), (0, 1), (1, 0), (1, 1)]
                elif wind_dir == "West":
                    corner_priorities = [(1, 0), (1, 1), (0, 0), (0, 1)]
                elif wind_dir == "North":
                    corner_priorities = [(0, 0), (1, 0), (0, 1), (1, 1)]
                elif wind_dir == "South":
                    corner_priorities = [(0, 1), (1, 1), (0, 0), (1, 0)]
                else:
                    corner_priorities = [(0, 0), (0, 1), (1, 0), (1, 1)]
                
                pos = None
                for xf, yf in corner_priorities:
                    cx_raw = margin if xf == 0 else sw - w - margin
                    cy_raw = margin if yf == 0 else sl - h - margin
                    cx, cy = snap_xy(cx_raw, cy_raw)
                    
                    # Ensure snapped coordinates are strictly within relaxed bounds
                    x_min_bound = snap(-_pass_tol)
                    if x_min_bound < -_pass_tol:
                        x_min_bound += CELL_SIZE
                    x_max_bound = snap(sw - w + _pass_tol)
                    if x_max_bound > sw - w + _pass_tol:
                        x_max_bound -= CELL_SIZE
                        
                    y_min_bound = snap(-_pass_tol)
                    if y_min_bound < -_pass_tol:
                        y_min_bound += CELL_SIZE
                    y_max_bound = snap(sl - h + _pass_tol)
                    if y_max_bound > sl - h + _pass_tol:
                        y_max_bound -= CELL_SIZE
                        
                    cx = max(x_min_bound, min(cx, x_max_bound))
                    cy = max(y_min_bound, min(cy, y_max_bound))
                    cx, cy = snap_xy(cx, cy)
                    
                    if _within_relaxed_bounds(cx, cy, w, h, sw, sl, tol=_pass_tol):
                        if not _overlaps_any("Flare", placed, cx, cy, w, h):
                            pos = (cx, cy, w, h)
                            break
                            
                # Fallback to BOUNDARY_TOLERANCE if strict bounds failed
                if pos is None and _pass_tol < BOUNDARY_TOLERANCE:
                    margin_fallback = -BOUNDARY_TOLERANCE
                    for xf, yf in corner_priorities:
                        cx_raw = margin_fallback if xf == 0 else sw - w - margin_fallback
                        cy_raw = margin_fallback if yf == 0 else sl - h - margin_fallback
                        cx, cy = snap_xy(cx_raw, cy_raw)
                        
                        x_min_bound = snap(-BOUNDARY_TOLERANCE)
                        if x_min_bound < -BOUNDARY_TOLERANCE:
                            x_min_bound += CELL_SIZE
                        x_max_bound = snap(sw - w + BOUNDARY_TOLERANCE)
                        if x_max_bound > sw - w + BOUNDARY_TOLERANCE:
                            x_max_bound -= CELL_SIZE
                            
                        y_min_bound = snap(-BOUNDARY_TOLERANCE)
                        if y_min_bound < -BOUNDARY_TOLERANCE:
                            y_min_bound += CELL_SIZE
                        y_max_bound = snap(sl - h + BOUNDARY_TOLERANCE)
                        if y_max_bound > sl - h + BOUNDARY_TOLERANCE:
                            y_max_bound -= CELL_SIZE
                            
                        cx = max(x_min_bound, min(cx, x_max_bound))
                        cy = max(y_min_bound, min(cy, y_max_bound))
                        cx, cy = snap_xy(cx, cy)
                        
                        if _within_relaxed_bounds(cx, cy, w, h, sw, sl, tol=BOUNDARY_TOLERANCE):
                            if not _overlaps_any("Flare", placed, cx, cy, w, h):
                                pos = (cx, cy, w, h)
                                break
            else:
                pos = _try_magnet_place(sw, sl, name, placed, prefer_near=prefer, filter_fn=f_fn,
                                        magnet_target=m_target, boundary_tol=_pass_tol)
            if pos is None:
                ok = False
                _last_debug["failed_at"] = name
                _last_debug["failed_section"] = "§3.5 Floated block placement"
                if "fail_counts" not in _last_debug:
                    _last_debug["fail_counts"] = {}
                _last_debug["fail_counts"][name] = _last_debug["fail_counts"].get(name, 0) + 1
                _last_debug["last_placed"] = {n: v for n, v in placed.items() if not n.startswith("_")}
                break
            placed[name] = pos
        if not ok:
            continue

        # Build output — filter out internal virtual zones (names starting with '_')
        blocks = [
            {"name": n, "x": bounds[0], "y": bounds[1], "width": bounds[2], "height": bounds[3],
             "color": BLOCK_COLORS.get(n, "#aaaaaa"),
             "rotated": (bounds[2], bounds[3]) != BLOCK_FOOTPRINTS.get(n, (bounds[2], bounds[3]))}
            for n, bounds in placed.items()
            if not n.startswith("_")
        ]

        # 4. RACK placement — comes AFTER floated blocks  [→ §3.6]
        # BEFORE perimeter/spurs/stubs (racks are more important than roads).
        # Step A: per-block buffer rectangles for Case 1 & Case 2 layouts.
        # Steps B-1..B-5 and C (spine + connector) — implemented.
        rack_buffers = compute_rack_buffers(blocks)
        spine_centerlines, candidate_points, active_cases, water_triangle = build_rack_spines(rack_buffers, blocks, sw, sl, ring_road, gate_spur, ring_spur)
        pb_ct_segments = list(spine_centerlines)
        water_cluster_segments = []
        rack_segments = list(spine_centerlines)

        valid_xs = set()
        valid_ys = set()
        for b in blocks:
            b_name = b["name"]
            if b_name in rack_buffers:
                if b_name in active_cases:
                    cases = [active_cases[b_name]]
                else:
                    cases = list(rack_buffers[b_name].keys())
                for case in cases:
                    rx, ry, rw, rh = rack_buffers[b_name][case]
                    valid_xs.update([rx, rx+rw])
                    valid_ys.update([ry, ry+rh])
        for pt in water_triangle:
            valid_xs.add(pt[0])
            valid_ys.add(pt[1])
        for seg in pb_ct_segments:
            valid_xs.update([seg[0][0], seg[1][0]])
            valid_ys.update([seg[0][1], seg[1][1]])

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

        # B-5: Water cluster spine  [→ §3.6.B-5]
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

        # Step C: Connect spines into one network  [→ §3.6.C-1]
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
                        for seg in spine_centerlines + water_cluster_segments:
                            set_extended_line_blocked(seg[0], seg[1], False)
                        for b in blocks:
                            b_name = b["name"]
                            if b_name in rack_buffers:
                                if b_name in active_cases:
                                    cases = [active_cases[b_name]]
                                else:
                                    cases = list(rack_buffers[b_name].keys())
                                for case in cases:
                                    rx, ry, rw, rh = rack_buffers[b_name][case]
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

                    # Build list of road segments to avoid running parallel to within 9m
                    road_segs = []
                    if ring_road:
                        for i in range(len(ring_road) - 1):
                            road_segs.append((ring_road[i], ring_road[i+1]))
                        road_segs.append((ring_road[-1], ring_road[0]))
                    if gate_spur:
                        for i in range(len(gate_spur) - 1):
                            road_segs.append((gate_spur[i], gate_spur[i+1]))
                    if ring_spur:
                        for i in range(len(ring_spur) - 1):
                            road_segs.append((ring_spur[i], ring_spur[i+1]))

                    horiz_roads = []
                    vert_roads = []
                    for p1, p2 in road_segs:
                        c1 = grid_c.world_to_cell(*p1)
                        c2 = grid_c.world_to_cell(*p2)
                        if c1[1] == c2[1]: # Horizontal road
                            y_val = p1[1]
                            x_min, x_max = min(p1[0], p2[0]), max(p1[0], p2[0])
                            horiz_roads.append((y_val, x_min, x_max))
                        elif c1[0] == c2[0]: # Vertical road
                            x_val = p1[0]
                            y_min, y_max = min(p1[1], p2[1]), max(p1[1], p2[1])
                            vert_roads.append((x_val, y_min, y_max))

                    # Exempt rack buffer boundary lines
                    exempt_horiz = []
                    exempt_vert = []
                    for b in blocks:
                        b_name = b["name"]
                        if b_name in rack_buffers:
                            if b_name in active_cases:
                                cases = [active_cases[b_name]]
                            else:
                                cases = list(rack_buffers[b_name].keys())
                            for case in cases:
                                rx, ry, rw, rh = rack_buffers[b_name][case]
                                if b_name == "Power Block":
                                    exempt_horiz.append((ry, rx - PB_RING_OFFSET, rx + rw + PB_RING_OFFSET))
                                    exempt_horiz.append((ry+rh, rx - PB_RING_OFFSET, rx + rw + PB_RING_OFFSET))
                                    exempt_vert.append((rx, ry - PB_RING_OFFSET, ry + rh + PB_RING_OFFSET))
                                    exempt_vert.append((rx+rw, ry - PB_RING_OFFSET, ry + rh + PB_RING_OFFSET))
                                else:
                                    exempt_horiz.append((ry, rx, rx+rw))
                                    exempt_horiz.append((ry+rh, rx, rx+rw))
                                    exempt_vert.append((rx, ry, ry+rh))
                                    exempt_vert.append((rx+rw, ry, ry+rh))

                    def forbid_move_hook(from_cell, di, dj):
                        to_cell = (from_cell[0] + di, from_cell[1] + dj)
                        p1 = (from_cell[0] * CELL_SIZE, from_cell[1] * CELL_SIZE)
                        p2 = (to_cell[0] * CELL_SIZE, to_cell[1] * CELL_SIZE)
                        
                        if dj == 0: # Horizontal move
                            for ey, ex0, ex1 in exempt_horiz:
                                if abs(p1[1] - ey) < 0.1:
                                    if ex0 - 0.1 <= min(p1[0], p2[0]) and max(p1[0], p2[0]) <= ex1 + 0.1:
                                        return False
                                        
                            move_x_min, move_x_max = min(p1[0], p2[0]), max(p1[0], p2[0])
                            for ry, rx0, rx1 in horiz_roads:
                                if min(move_x_max, rx1) >= max(move_x_min, rx0) - 0.1:
                                    if abs(p1[1] - ry) < 9.0 - 0.1:
                                        return True
                                        
                        elif di == 0: # Vertical move
                            for ex, ey0, ey1 in exempt_vert:
                                if abs(p1[0] - ex) < 0.1:
                                    if ey0 - 0.1 <= min(p1[1], p2[1]) and max(p1[1], p2[1]) <= ey1 + 0.1:
                                        return False
                                        
                            move_y_min, move_y_max = min(p1[1], p2[1]), max(p1[1], p2[1])
                            for rx, ry0, ry1 in vert_roads:
                                if min(move_y_max, ry1) >= max(move_y_min, ry0) - 0.1:
                                    if abs(p1[0] - rx) < 9.0 - 0.1:
                                        return True
                                        
                        return False

                    path = astar(
                        grid_c,
                        start_cells,
                        goal_cells,
                        turn_penalty=10.0,
                        width_cells=0,
                        allow_diagonal=False,
                        forbid_move=forbid_move_hook
                    )
                    return path

                path = run_routing(restricted=True)
                if not path:
                    path = run_routing(restricted=False)

                if path:
                    path_pts = [snap_pt(*grid_c.cell_to_world(*c)) for c in path]
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
                    return path[-1], new_segs
                return None, []

            # 1. PB/CT spine network to water cluster spine
            found_goal_1, new_segs_1 = route_between(spine_centerlines, water_cluster_segments)
            water_cluster_segments.extend(new_segs_1)
            
            # Second connection stage removed (closest PB/CT connection only)
            pass

            # Step C-2: Flare Pipe Rack  [→ §3.6.C-2]
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
                    flare_boundary_segs = [
                        [(fx0, fy0), (fx1, fy0)], # Bottom
                        [(fx1, fy0), (fx1, fy1)], # Right
                        [(fx0, fy1), (fx1, fy1)], # Top
                        [(fx0, fy0), (fx0, fy1)]  # Left
                    ]
                    
                    # Target segments: rack segments excluding segments that touch pb_center
                    target_segs = []
                    for seg in rack_segments:
                        p1, p2 = seg
                        d1 = math.hypot(p1[0] - pb_cx, p1[1] - pb_cy)
                        d2 = math.hypot(p2[0] - pb_cx, p2[1] - pb_cy)
                        if d1 > 0.1 and d2 > 0.1:
                            target_segs.append(seg)
                            
                    route_between(flare_boundary_segs, target_segs)

                # Add to rack_buffers for dashboard visualization
                rack_buffers["Flare"] = {"case1_rack": (fx0, fy0, fw + 2 * flare_offset, fh + 2 * flare_offset)}

        computed_buffers = compute_unsnapped_buffers(placed)
        perimeter_segments_raw = []
        group_a_segments_raw = generate_group_a_access(computed_buffers, placed, sw, sl, gate_pt[0], gate_pt[1])
        all_segments_raw = group_a_segments_raw
        
        pb_network = []
        if ring_road:
            for i in range(len(ring_road) - 1):
                pb_network.append((ring_road[i], ring_road[i+1]))
            pb_network.append((ring_road[-1], ring_road[0]))
        if gate_spur:
            for i in range(len(gate_spur) - 1):
                pb_network.append((gate_spur[i], gate_spur[i+1]))
        if ring_spur:
            for i in range(len(ring_spur) - 1):
                pb_network.append((ring_spur[i], ring_spur[i+1]))
                
        all_segments_cleaned = cleanup_parallel_segments(all_segments_raw, sw, sl, computed_buffers, ref_segs=pb_network, tol=17.0, gdz=gate_death_zone, pb_cx=pb_cx)

        outer_loop, outer_loop_pts = compute_buffer_union_contour(computed_buffers, sw, sl)
        boom_barrier = []
        gh = next((b for b in blocks if b["name"] == "Gate House"), None)
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
        _last_debug["failed_at"] = None
        _last_debug["failed_section"] = None
        _last_debug["boundary_tol_used"] = _pass_tol
        _last_debug["boundary_pass_label"] = _pass_label
        return {
            "blocks":          blocks,
            "boom_barrier":    boom_barrier,
            "ring_road":       ring_road,
            "perimeter_segments_raw": perimeter_segments_raw,
            "group_a_segments_raw": group_a_segments_raw,
            "all_segments_cleaned": all_segments_cleaned,
            "outer_loop":   outer_loop,
            "outer_loop_pts":  outer_loop_pts,
            "gate_spur":       gate_spur,
            "ring_spur":       ring_spur,
            "rack_buffers":    rack_buffers,
            "rack_segments":   rack_segments,
            "rack_candidates": candidate_points,
            "active_rack_cases": active_cases,
            "water_triangle":  water_triangle,
            "spine_centerlines": spine_centerlines,
            "water_cluster_segments": water_cluster_segments,
            "gate_point":      gate_pt,
            "gate_death_zone": gate_death_zone,
            "pb_center":       (pb_cx, pb_cy),
            "cell_size":       CELL_SIZE,
            "block_buffer":    BLOCK_BUFFER,
            "pb_ring_offset":  PB_RING_OFFSET,
            "perimeter_cl":    PERIMETER_CL_DIST,
            "computed_buffers_debug": computed_buffers,
        }
        # Inner loop (max_pool) exhausted without finding a layout for this pass.
        # Fall through to the next pass (relaxed tolerance).

    return None

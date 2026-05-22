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
        return ROAD_W_RACK_OFFSET   # 14
    if not a_rack and not b_rack:
        return ROAD_BUFFER          # 8
    return B2B_W_RACK_OFFSET        # 28


def _overlaps_any(name, placed, x, y, w, h):
    """Per-pair edge-to-edge gap, keyed on rack membership via `pair_min_gap`.

    Virtual zones (names with `_` prefix — `_pb_ring_zone`, `_gate_spur_zone`,
    `_ring_spur_zone`) use gap=0 because their rectangle already includes the
    8m road buffer; a block touching the zone edge is already 8m from the
    road centerline."""
    for bname, (bx, by, bw, bh) in placed.items():
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
                       samples_per_side=7, lateral_inset=4):
    """Generate (x, y) candidates by snapping a block (w×h, named `name`) at
    the pair-appropriate magnet distance against each side of every real
    placed block. Honors relaxed bounds (`_within_relaxed_bounds`) and the
    per-pair collision check (`_overlaps_any`)."""
    cands = []
    for tname, (tx, ty, tw, th) in placed.items():
        if tname.startswith("_"):
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


def _try_magnet_place(sw, sl, name, placed, prefer_near=None):
    """Place a floated block by magnetizing to a previously placed block.

    Tries both orientations. Returns (x, y, w, h) or None when no candidate
    survives bounds + collision checks. `prefer_near` keeps the existing
    top-10%-closest selection so blocks still cluster near PB."""
    base_w, base_h = BLOCK_FOOTPRINTS[name]
    orientations = [(base_w, base_h)]
    if base_w != base_h:
        orientations.append((base_h, base_w))

    valid = []
    for w, h in orientations:
        for x, y in _magnet_candidates(name, w, h, placed, sw, sl):
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


def build_gate_spur(gate_pt, perimeter_road):
    """Short primary-road segment connecting the gate (on the boundary) to the
    perimeter road centerline. Always axis-aligned (perpendicular drop): paths
    use only straight lines, so we project the gate orthogonally to whichever
    perimeter edge it sits outside of, rather than sampling for the nearest
    polyline point (which can be 1m off-axis due to the 2m sampling step)."""
    gx, gy = gate_pt
    xs = [p[0] for p in perimeter_road]
    ys = [p[1] for p in perimeter_road]
    px_min, px_max = min(xs), max(xs)
    py_min, py_max = min(ys), max(ys)
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


def build_ring_spur(site_w, site_l, ring_road, perimeter_road, blocks, gate_pt):
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
    pxs, pys = zip(*perimeter_road)
    rxmin, rxmax = min(rxs), max(rxs)
    rymin, rymax = min(rys), max(rys)
    pxmin, pxmax = min(pxs), max(pxs)
    pymin, pymax = min(pys), max(pys)

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

def find_nearest_road_point(block_center, road_polyline):
    """Find the point along the road polyline closest to block_center."""
    cx, cy = block_center
    best_pt = None
    best_dist = math.inf
    for i in range(len(road_polyline) - 1):
        pts = get_line_points(road_polyline[i], road_polyline[i+1], step=2.0)
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
    _add_cell_sequence(G, _rasterise_polyline(grid, perimeter_road), "primary",   grid)
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
        perimeter_road = build_perimeter_road(sw, sl)
        fixed_blocks_so_far = [
            {"name": n, "x": x, "y": y, "width": w, "height": h}
            for n, (x, y, w, h) in placed.items() if not n.startswith("_")
        ]
        gate_spur = build_gate_spur(gate_pt, perimeter_road)
        ring_spur = build_ring_spur(sw, sl, ring_road, perimeter_road,
                                    fixed_blocks_so_far, gate_pt)
        for zone_name, line in (("_gate_spur_zone", gate_spur),
                                ("_ring_spur_zone", ring_spur)):
            rect = _spur_exclusion_rect(line, buffer=ROAD_BUFFER)
            if rect:
                placed[zone_name] = rect

        # 4. Floated blocks — magnet placement.
        # Each block snaps against a previously placed block's side at the
        # pair-appropriate distance (8 / 14 / 28 m, see pair_min_gap). Order
        # is biggest-first; prefer_near keeps the "cluster around PB" pull.
        gh_x, gh_y = placed["Gate House"][:2]
        admin_anchor = ((gh_x + pb_cx) / 2, (gh_y + pb_cy) / 2)

        floated_order = [
            ("Cooling Tower",   (pb_cx, pb_cy)),
            ("WT/WWT",          (pb_cx, pb_cy)),
            ("Warehouse",       (pb_cx, pb_cy)),
            ("Flare",           (pb_cx, pb_cy)),
            ("Admin Building",  admin_anchor),
            ("Demi Water Tank", None),
        ]

        ok = True
        for name, prefer in floated_order:
            pos = _try_magnet_place(sw, sl, name, placed, prefer_near=prefer)
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
        rack_segments = []   # populated by Steps B/C in a follow-up

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
            pt_peri = find_nearest_road_point(bc, perimeter_road)

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

        # 7. Road graph + 2-path verification + pruning (Steps 1.5-1.6)
        # gate_spur + ring_spur already built in step 3b (so their 8m buffer
        # constrains floated-block placement). Reused here as primary edges.
        graph_grid = Grid(sw, sl, cell_size=CELL_SIZE)
        road_graph, gate_node = build_road_graph(
            graph_grid, ring_road, perimeter_road, stubs, gate_pt,
            gate_spur=gate_spur, ring_spur=ring_spur,
        )
        pruned_graph, used_edges, kept_traces = verify_and_prune(
            road_graph, gate_node, stubs, graph_grid,
        )
        fire_segments, secondary_segs = classify_edges(pruned_graph, graph_grid)

        # Segments that exist in the full graph but were pruned (for debug viz)
        pruned_segments = []
        kept = set(tuple(sorted([u, v])) for u, v in pruned_graph.edges())
        for u, v in road_graph.edges():
            if tuple(sorted([u, v])) not in kept:
                pruned_segments.append((graph_grid.cell_to_world(*u),
                                        graph_grid.cell_to_world(*v)))

        # Per-block trace = the SHORTER of the two candidate paths (Power Block excluded)
        path_traces = [
            {"block": bname, "via": tr["via"],
             "world": [graph_grid.cell_to_world(*c) for c in tr["cells"]]}
            for bname, tr in kept_traces.items()
        ]


        return {
            "blocks":          blocks,
            "ring_road":       ring_road,
            "perimeter_road":  perimeter_road,
            "gate_spur":       gate_spur,
            "ring_spur":       ring_spur,
            "rack_buffers":    rack_buffers,
            "rack_segments":   rack_segments,
            "stubs":           stubs,
            "road_graph":      pruned_graph,
            "fire_segments":   fire_segments,
            "secondary_segs":  secondary_segs,
            "pruned_segments": pruned_segments,
            "path_traces":     path_traces,
            "gate_point":      gate_pt,
            "gate_node":       gate_node,
            "pb_center":       (pb_cx, pb_cy),
            "cell_size":       CELL_SIZE,
            "block_buffer":    BLOCK_BUFFER,
            "pb_ring_offset":  PB_RING_OFFSET,
            "perimeter_cl":    PERIMETER_CL_DIST,
        }

    return None

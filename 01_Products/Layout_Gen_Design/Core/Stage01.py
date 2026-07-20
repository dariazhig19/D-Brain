"""Phase 06 — Steps 1.1–1.3: Grid-first block placement + fire road sketches.

Steps covered:
  1.1  2m grid setup, all blocks snap to grid
  1.2  Placement sequence + fire road geometry
  1.3  Block buffer: 15m between block edges
"""

import random
import math
import time
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

_time_budget = 25.0
_t_start = 0.0

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


def _boom_edge_and_mid(boom, gh_rect):  # → §3.4.B (polygon)
    """From the CAD boom line + gate house, derive the legacy ``bb_edge`` and the
    boom midpoint ``bb_mid``.

    ``bb_edge`` ∈ {N,S,E,W} = which gate-house side the boom sits on (a vertical
    boom sits on the N or S side; a horizontal boom on the E or W side, chosen by
    which side of the gate-house centre the boom lies). ``bb_mid`` is the boom's
    own midpoint, so the gate spur crosses the boom exactly where it is drawn.
    This lets the ORIGINAL gate-spur construction run unchanged on the polygon."""
    (x0, y0), (x1, y1) = boom[0], boom[1]
    mid = ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
    gx, gy, gw, gh = gh_rect
    gcx, gcy = gx + gw / 2.0, gy + gh / 2.0
    if abs(x1 - x0) <= abs(y1 - y0):          # vertical boom → N / S side
        return ("N" if mid[1] >= gcy else "S"), mid
    return ("E" if mid[0] >= gcx else "W"), mid   # horizontal boom → E / W side


def _place_flare_on_polygon(plot, placed, wind_dir, pass_tol):  # → §3.5.C (polygon)
    """Place the Flare at the leeward CORNER (vertex) of the plot polygon.

    Picks the polygon vertex furthest in the leeward (downwind) direction, breaking
    ties by choosing the vertex furthest from the Admin Building's preferred area, then
    nudges the footprint inward toward the plot center until it fits inside and
    clears other blocks. Returns (x, y, w, h) or None."""
    w, h = BLOCK_FOOTPRINTS["Flare"]
    cx, cy = plot.centroid

    # Compute a reference point for the Admin Building/Gate area to maximize distance from
    ref_pt = None
    gh = placed.get("Gate House")
    pb = placed.get("Power Block")
    if gh and pb:
        gh_cx, gh_cy = gh[0] + gh[2]/2.0, gh[1] + gh[3]/2.0
        pb_cx, pb_cy = pb[0] + pb[2]/2.0, pb[1] + pb[3]/2.0
        ref_pt = ((gh_cx + pb_cx) / 2.0, (gh_cy + pb_cy) / 2.0)
    elif gh:
        ref_pt = (gh[0] + gh[2]/2.0, gh[1] + gh[3]/2.0)
    elif pb:
        ref_pt = (pb[0] + pb[2]/2.0, pb[1] + pb[3]/2.0)

    def is_leeward(v):
        cx, cy = plot.centroid
        if wind_dir == "East":  return v[0] <= cx
        if wind_dir == "West":  return v[0] >= cx
        if wind_dir == "North": return v[1] <= cy
        if wind_dir == "South": return v[1] >= cy
        return True

    def leeward_score(v):
        # higher = more leeward
        if wind_dir == "East":    val = -(v[0])   # downwind = -x
        elif wind_dir == "West":  val =  (v[0])
        elif wind_dir == "North": val = -(v[1])
        elif wind_dir == "South": val =  (v[1])
        else: val = -(v[1])
        
        dist = 0.0
        if ref_pt:
            dist = math.hypot(v[0] - ref_pt[0], v[1] - ref_pt[1])
            
        # Return tuple: (is_leeward, distance_to_admin_area, leeward_val)
        return (is_leeward(v), dist, val)

    for v in sorted(plot.vertices, key=leeward_score, reverse=True):
        dx, dy = cx - v[0], cy - v[1]
        d = math.hypot(dx, dy) or 1.0
        ux, uy = dx / d, dy / d
        for t in (35, 45, 55, 70, 90, 110):
            ccx, ccy = v[0] + ux * t, v[1] + uy * t
            x, y = snap_xy(ccx - w / 2, ccy - h / 2)
            if (plot.contains_rect(x, y, w, h, tol=pass_tol)
                    and not _overlaps_any("Flare", placed, x, y, w, h)):
                return (x, y, w, h)
    return None


def _within_relaxed_bounds(x, y, w, h, sw, sl, tol=BOUNDARY_TOLERANCE, plot=None):  # → §3.5.A
    """Allow placement up to `tol` metres outside the plot on any side.

    Polygon migration: when `plot` (a `Core.Plot.Plot`) is given, the check runs
    against the polygon (`plot.contains_rect`) including diagonal sides. When
    `plot` is None this is the original rectangle test, unchanged."""
    if plot is not None:
        return plot.contains_rect(x, y, w, h, tol)
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
               x_bounds=None, y_bounds=None, plot=None, plot_tol=0):
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
            # Polygon migration: the buffered rectangle must also stay inside the
            # plot polygon (diagonal sides). No-op when plot is None.
            if plot is not None and not plot.contains_rect(
                    x - buffer, y - buffer, w + 2 * buffer, h + 2 * buffer, tol=plot_tol):
                continue
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
                       samples_per_side=7, lateral_inset=4, target=None, boundary_tol=BOUNDARY_TOLERANCE,
                       plot=None):
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
            if not _within_relaxed_bounds(x, y, w, h, sw, sl, tol=boundary_tol, plot=plot):
                continue
            if _overlaps_any(name, placed, x, y, w, h):
                continue
            cands.append((x, y))
    return cands


def _boundary_offset_candidates(name, w, h, placed, sw, sl, plot, gap,  # → §3.5
                                boundary_tol=BOUNDARY_TOLERANCE):
    """Candidates whose ROAD BUFFER outer edge sits exactly `gap` metres
    inside the plot boundary, sampled every ~8 m along each polygon edge.
    Used for blocks that prefer hugging the boundary (Cooling Tower)."""
    if plot is None:
        return []
    b_off = 16.0 if name in RACK_BLOCKS else 8.0
    d = b_off + gap
    cands = []
    for e in plot.edges:
        (ex1, ey1), (ex2, ey2) = e["p1"], e["p2"]
        nx, ny = e["normal"]  # inward
        elen = math.hypot(ex2 - ex1, ey2 - ey1)
        steps = max(1, int(elen // 8))
        for i in range(steps + 1):
            t = i / steps
            qx = ex1 + t * (ex2 - ex1)
            qy = ey1 + t * (ey2 - ey1)
            # place the rect's support corner (the one facing this edge)
            # at distance d inward from the edge line
            x = qx + nx * d - (0.0 if nx >= 0 else w)
            y = qy + ny * d - (0.0 if ny >= 0 else h)
            x, y = snap_xy(x, y)
            if not _within_relaxed_bounds(x, y, w, h, sw, sl, tol=boundary_tol, plot=plot):
                continue
            if _overlaps_any(name, placed, x, y, w, h):
                continue
            # NOTE: the full buffer may still poke out through an ADJACENT
            # edge near plot corners — deliberately NOT filtered here. In
            # tight plots no candidate may have the whole buffer inside; the
            # caller's scoring (|gap − 4| with a penalty for gap < 0) then
            # picks the least-violating position closest to the 4 m target.
            cands.append((x, y))
    return cands


def _empty_space_candidates(name, w, h, placed, sw, sl,  # → §3.5
                            step=8, boundary_tol=BOUNDARY_TOLERANCE, plot=None):
    """Generate (x, y) candidates by scanning a coarse grid over the whole plot
    (not magnetized to any block). Honors relaxed bounds and the collision check.
    Used as the last-resort placement when magnetizing to every block fails."""
    cands = []
    x = 0.0
    while x <= sw - w + 0.1:
        y = 0.0
        while y <= sl - h + 0.1:
            sx, sy = snap_xy(x, y)
            if (_within_relaxed_bounds(sx, sy, w, h, sw, sl, tol=boundary_tol, plot=plot)
                    and not _overlaps_any(name, placed, sx, sy, w, h)):
                cands.append((sx, sy))
            y += step
        x += step
    return cands


def _try_magnet_place(sw, sl, name, placed, prefer_near=None, filter_fn=None, magnet_target=None,  # → §3.5
                      boundary_tol=BOUNDARY_TOLERANCE, plot=None):
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
                                       boundary_tol=boundary_tol, plot=plot):
            if filter_fn is None or filter_fn(x, y, w, h):
                valid.append((x, y, w, h))

    # §3.5 CT boundary preference: also OFFER positions along the plot
    # boundary with the road buffer exactly 4 m inside it — the magnet scan
    # alone rarely produces such candidates, so without this the preference
    # has nothing to select.
    if name == "Cooling Tower" and plot is not None:
        for w, h in orientations:
            for x, y in _boundary_offset_candidates(name, w, h, placed, sw, sl, plot, 4.0,
                                                    boundary_tol=boundary_tol):
                if filter_fn is None or filter_fn(x, y, w, h):
                    valid.append((x, y, w, h))

    # Fallback to any valid magnet target if the specified target fails
    if magnet_target is not None and not valid:
        for w, h in orientations:
            for x, y in _magnet_candidates(name, w, h, placed, sw, sl, target=None,
                                           boundary_tol=boundary_tol, plot=plot):
                if filter_fn is None or filter_fn(x, y, w, h):
                    valid.append((x, y, w, h))

    # Last resort: place in EMPTY SPACE (not magnetized) so the block lands
    # somewhere valid instead of failing the whole layout. Prefer the zone
    # filter, but drop it if nothing in-zone fits.
    if not valid:
        empty = []
        for w, h in orientations:
            empty += [(x, y, w, h) for x, y in
                      _empty_space_candidates(name, w, h, placed, sw, sl, boundary_tol=boundary_tol, plot=plot)]
        in_zone = [c for c in empty if filter_fn is None or filter_fn(c[0], c[1], c[2], c[3])]
        valid = in_zone if in_zone else empty

    if not valid:
        return None
    if name == "Cooling Tower":
        # §3.5 CT boundary preference: CT prefers sitting with its ROAD
        # BUFFER ~4 m from the (temporary) plot boundary; `prefer_near`
        # (closeness to PB) is only the tiebreak.
        b_off = 16.0 if name in RACK_BLOCKS else 8.0
        CT_BOUNDARY_GAP = 4.0

        def _ct_key(v):
            x, y, w, h = v
            corners = ((x - b_off, y - b_off), (x + w + b_off, y - b_off),
                       (x - b_off, y + h + b_off), (x + w + b_off, y + h + b_off))
            if plot is not None:
                gap = min(plot.signed_dist_to_boundary(px, py) for px, py in corners)
            else:
                gap = min(x - b_off, y - b_off,
                          sw - (x + w + b_off), sl - (y + h + b_off))
            d_pref = ((x + w / 2 - prefer_near[0]) ** 2 + (y + h / 2 - prefer_near[1]) ** 2
                      if prefer_near is not None else 0.0)
            dev = abs(gap - CT_BOUNDARY_GAP)
            if gap < 0:
                dev += 100.0  # buffer pokes OUTSIDE the plot — strongly avoid
            return (dev, d_pref)

        valid.sort(key=_ct_key)
        return random.choice(valid[:max(1, len(valid) // 10)])
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
    return [], {}


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

# §3.6.B B-1 — weight of the "PB side faces RAW" term relative to the PB↔CT
# connection gap when jointly selecting the spine sides. Kept small so the gap
# (which drives the realized spine length) dominates and RAW only breaks ties.
# RAW is only a tie-breaker among the sides that already face the other block
# (see the mutual-facing filter in build_rack_spines).
SPINE_RAW_WEIGHT = 0.25

# §3.6.C-3 — rack segments shorter than this (metres) are pruned as stubs.
MIN_RACK_SEG_LEN = 6.0


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


def mark_rack_obstacles(grid, blocks, rack_buffers, active_cases, exclude=None,
                        min_inflate=0.0):  # → §3.6 (buffer-corridor routing)
    """Mark routing obstacles so a rack path is forced onto the active
    rack-buffer LINE and cannot cut through a block's footprint→buffer gap.

    For each rack block the footprint is inflated to one cell INSIDE its active
    rack-buffer line, so the buffer-line ring itself stays free for the path to
    travel along. Non-rack blocks (and rack blocks without an active case) keep
    plain footprint marking. `exclude` is an optional set of block names left
    completely unmarked (e.g. the Power Block for the main-rack-stepping search).

    ``min_inflate`` is a floor applied to EVERY marked block (e.g. the Case 1
    rack-buffer offset minus one cell) so the PB↔CT spine routes around every
    block's minimum rack buffer, not just its bare footprint.
    """
    exclude = exclude or set()
    cs = grid.cell_size
    for b in blocks:
        name = b["name"]
        if name in exclude:
            continue
        rect = None
        if name in rack_buffers and name in active_cases:
            rect = rack_buffers[name].get(active_cases[name])
        if rect is not None:
            offset = b["x"] - rect[0]          # active rack-buffer offset
            grid.mark_building(b, inflate_m=max(min_inflate, offset - cs))
        else:
            grid.mark_building(b, inflate_m=min_inflate)


def cleanup_ct_free_ends(ct_half, rack_segments, anchor_pts=()):  # → §3.6.C-3
    """Trim dangling free ends off a spine half (`best_ct_half`).

    After all rack routing, the half may stick out past the points where other
    rack segments actually connect to it. Find every junction (a point where
    another segment meets the half), then shorten the half to span only between
    the outermost junctions — removing the free end(s). If fewer than two distinct
    junctions exist (so both ends are free / only a single touch), the half is
    redundant → return None to prune it entirely.

    ``anchor_pts`` are extra points (e.g. the water-triangle connection points on
    RAW/Demi/WWT rack buffers) that count as junctions and must be kept, so the
    trim never disconnects a block it serves.

    Returns the trimmed segment, the original (unchanged) segment, or None.
    """
    (hx0, hy0), (hx1, hy1) = ct_half
    eps = 0.1
    vertical = abs(hx0 - hx1) < eps
    js = []
    for seg in rack_segments:
        if seg is ct_half:
            continue
        (ax, ay), (bx, by) = seg
        if vertical:
            if abs(ay - by) < eps:                                  # horizontal other
                if (min(hy0, hy1) - eps <= ay <= max(hy0, hy1) + eps
                        and min(ax, bx) - eps <= hx0 <= max(ax, bx) + eps):
                    js.append(ay)
            elif abs(ax - hx0) < eps:                               # collinear vertical other
                for yy in (ay, by):
                    if min(hy0, hy1) - eps <= yy <= max(hy0, hy1) + eps:
                        js.append(yy)
                for yy in (hy0, hy1):
                    if min(ay, by) - eps <= yy <= max(ay, by) + eps:
                        js.append(yy)
        else:
            if abs(ax - bx) < eps:                                  # vertical other
                if (min(hx0, hx1) - eps <= ax <= max(hx0, hx1) + eps
                        and min(ay, by) - eps <= hy0 <= max(ay, by) + eps):
                    js.append(ax)
            elif abs(ay - hy0) < eps:                               # collinear horizontal other
                for xx in (ax, bx):
                    if min(hx0, hx1) - eps <= xx <= max(hx0, hx1) + eps:
                        js.append(xx)
                for xx in (hx0, hx1):
                    if min(ax, bx) - eps <= xx <= max(ax, bx) + eps:
                        js.append(xx)

    # Extra anchors (e.g. water-triangle connection points) lying on this half
    # count as junctions so the trim keeps the part that reaches them.
    for (px, py) in anchor_pts:
        if vertical:
            if abs(px - hx0) < eps and min(hy0, hy1) - eps <= py <= max(hy0, hy1) + eps:
                js.append(py)
        else:
            if abs(py - hy0) < eps and min(hx0, hx1) - eps <= px <= max(hx0, hx1) + eps:
                js.append(px)

    distinct = sorted({round(j, 3) for j in js})
    if len(distinct) < 2:
        return None
    lo, hi = distinct[0], distinct[-1]
    if vertical:
        return [(hx0, lo), (hx0, hi)]
    return [(lo, hy0), (hi, hy0)]


def segments_intersect(p1, p2, p3, p4):
    def ccw(a, b, c):
        return (c[1]-a[1])*(b[0]-a[0]) > (b[1]-a[1])*(c[0]-a[0])
    return ccw(p1, p3, p4) != ccw(p2, p3, p4) and ccw(p1, p2, p3) != ccw(p1, p2, p4)


def line_intersects_pb(p1, p2, pb_rect):
    pb_x, pb_y, pb_w, pb_h = pb_rect
    def is_inside_pb(p):
        return pb_x <= p[0] <= pb_x + pb_w and pb_y <= p[1] <= pb_y + pb_h
    if is_inside_pb(p1) or is_inside_pb(p2):
        return True
    sides = [
        ((pb_x, pb_y), (pb_x + pb_w, pb_y)),
        ((pb_x + pb_w, pb_y), (pb_x + pb_w, pb_y + pb_h)),
        ((pb_x, pb_y + pb_h), (pb_x + pb_w, pb_y + pb_h)),
        ((pb_x, pb_y), (pb_x, pb_y + pb_h))
    ]
    for s1, s2 in sides:
        if segments_intersect(p1, p2, s1, s2):
            return True
    return False


def closest_points_between_networks(segs_a, segs_b):
    def get_segment_points(seg, step=2):
        p1, p2 = seg
        x1, y1 = p1
        x2, y2 = p2
        pts = [p1, p2]
        if abs(x1 - x2) < 0.1: # Vertical
            y_min, y_max = min(y1, y2), max(y1, y2)
            y = snap(y_min)
            while y <= y_max:
                if y_min <= y <= y_max:
                    pts.append((x1, y))
                y += step
        else: # Horizontal
            x_min, x_max = min(x1, x2), max(x1, x2)
            x = snap(x_min)
            while x <= x_max:
                if x_min <= x <= x_max:
                    pts.append((x, y1))
                x += step
        return list(set(pts))

    best_dist = float('inf')
    best_pair = None
    for seg_a in segs_a:
        pts_a = get_segment_points(seg_a)
        for seg_b in segs_b:
            pts_b = get_segment_points(seg_b)
            for pa in pts_a:
                for pb in pts_b:
                    d = abs(pa[0] - pb[0]) + abs(pa[1] - pb[1])
                    if d < best_dist:
                        best_dist = d
                        best_pair = (pa, pb)
    return best_pair


def _remove_tiny_jogs(segments, max_jog=2.5):  # → §3.6.C-3 (clean 1-grid jogs)
    """Remove tiny (<= max_jog) perpendicular jogs that offset two otherwise
    collinear axis-aligned rack segments by one grid cell (an A* snapping
    artefact, e.g. a y=101 run and a y=102 run bridged by a 1 m vertical jog).

    The jog's two endpoints must each have exactly ONE other segment, both
    perpendicular to the jog. The jog is dropped and the segment on one side is
    shifted onto the other side's line; any segment attached at the shifted far
    end is pulled along (only if it is perpendicular, so it just lengthens). If
    any condition fails the jog is left untouched. Returns the cleaned list."""
    segs = [[tuple(s[0]), tuple(s[1])] for s in segments]

    def near(a, b):
        return abs(a[0] - b[0]) < 0.6 and abs(a[1] - b[1]) < 0.6

    def is_vert(s):
        return abs(s[0][0] - s[1][0]) < abs(s[0][1] - s[1][1])

    def nbrs(node, exclude):
        out = []
        for si in range(len(segs)):
            if si == exclude:
                continue
            for e in (0, 1):
                if near(segs[si][e], node):
                    out.append((si, e))
        return out

    changed = True
    guard = 0
    while changed and guard < 100:
        changed = False
        guard += 1
        for ji in range(len(segs)):
            J = segs[ji]
            jlen = math.hypot(J[1][0] - J[0][0], J[1][1] - J[0][1])
            if jlen < 0.1 or jlen > max_jog:
                continue
            jvert = is_vert(J)
            for a_i, b_i in ((0, 1), (1, 0)):
                A, B = J[a_i], J[b_i]
                an, bn = nbrs(A, ji), nbrs(B, ji)
                if len(an) != 1 or len(bn) != 1:
                    continue
                bi, bend = bn[0]
                Sb = segs[bi]
                if is_vert(Sb) == jvert:          # B-neighbour must be perpendicular to J
                    continue
                dx = (A[0] - B[0]) if not jvert else 0.0
                dy = (A[1] - B[1]) if jvert else 0.0
                far = Sb[1 - bend]
                far_attached, ok = [], True
                for si in range(len(segs)):
                    if si == bi:
                        continue
                    for e in (0, 1):
                        if near(segs[si][e], far):
                            if is_vert(segs[si]) == is_vert(Sb):   # parallel → would go diagonal
                                ok = False
                            far_attached.append((si, e))
                if not ok:
                    continue
                # Snap: shift the whole B-side segment + pull the perpendicular(s) at its far end.
                segs[bi] = [(Sb[0][0] + dx, Sb[0][1] + dy), (Sb[1][0] + dx, Sb[1][1] + dy)]
                for si, e in far_attached:
                    segs[si][e] = (segs[si][e][0] + dx, segs[si][e][1] + dy)
                del segs[ji]
                changed = True
                break
            if changed:
                break
    return [tuple(map(tuple, s)) for s in segs]


def _mask_grid_to_plot(grid, plot):  # → §3.6 (polygon)
    """Block every grid cell whose centre lies OUTSIDE the plot polygon.

    Makes rack A* routing treat the area beyond a diagonal/cut edge as solid, so a
    rack can never run outside the plot. No-op when ``plot`` is None (rectangle).
    Vectorised: a cell is inside iff it is on the interior side of every edge."""
    if plot is None:
        return
    import numpy as np
    cs = grid.cell_size
    xs = (np.arange(grid.ncols) + 0.5) * cs       # cell-centre x per column
    ys = (np.arange(grid.nrows) + 0.5) * cs       # cell-centre y per row
    inside = np.ones((grid.ncols, grid.nrows), dtype=bool)
    for e in plot.edges:
        nx, ny = e["normal"]
        px, py = e["p1"]
        d = (xs[:, None] - px) * nx + (ys[None, :] - py) * ny   # signed dist, + = interior
        inside &= (d >= 0)
    grid.blocked |= ~inside


def build_rack_spines(rack_buffers, blocks, sw, sl, ring_road=None, gate_spur=None, ring_spur=None, plot=None):  # → §3.6.B (B-1..B-4)
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

    def get_spine_side(rect, block_cx, block_cy, name):
        x, y, w, h = rect
        tx, ty = (ct_cx, ct_cy) if name == "Power Block" else (pb_cx, pb_cy)
        dx = tx - block_cx
        dy = ty - block_cy
        
        if abs(dx) > abs(dy):
            return [(x, y), (x, y+h)] if tx < block_cx else [(x+w, y), (x+w, y+h)]
        else:
            return [(x, y), (x+w, y)] if ty < block_cy else [(x, y+h), (x+w, y+h)]

    def choose_case(name, rect_c1, rect_c2, cx, cy):
        # Check all 4 sides of the Case 2 buffer rectangle against the plot boundary.
        # If any side is within the 10.0m margin or outside, reject Case 2.
        x, y, w, h = rect_c2
        margin = 10.0
        if (x < margin or (x + w) > sw - margin or
            y < margin or (y + h) > sl - margin):
            return "case1_rack"

        # Selected side of Case 2
        side_c2 = get_spine_side(rect_c2, cx, cy, name)
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
                
        # Check if the Case 2 spine side intersects with any other block (excluding the spine target blocks themselves)
        other_blocks = [b for b in blocks if b["name"] not in (name, "Power Block", "Cooling Tower")]
        for b in other_blocks:
            if line_intersects_pb(p1, p2, (b["x"], b["y"], b["width"], b["height"])):
                return "case1_rack"

        if dist < margin or is_outside:
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
        candidate_points = []
        raw_candidates = []
        
        def get_corners(rect):
            x, y, w, h = rect
            return [(x, y), (x+w, y), (x+w, y+h), (x, y+h)]

        def is_inside(c):
            return 0 <= c[0] <= sw and 0 <= c[1] <= sl

        rect = rack_buffers.get("RAW Water Tank", {}).get(active_cases.get("RAW Water Tank"))
        if rect:
            corners = get_corners(rect)
            corners = [c for c in corners if is_inside(c)]
            ref_pt = (sw/2, sl/2)
            corners.sort(key=lambda c: (c[0]-ref_pt[0])**2 + (c[1]-ref_pt[1])**2)
            raw_candidates = corners[:2]
            candidate_points.extend(raw_candidates)

        demi_candidates = []
        rect = rack_buffers.get("Demi Water Tank", {}).get(active_cases.get("Demi Water Tank"))
        if rect:
            corners = get_corners(rect)
            corners = [c for c in corners if is_inside(c)]
            ref_pt = (sw/2, sl/2)
            corners.sort(key=lambda c: (c[0]-ref_pt[0])**2 + (c[1]-ref_pt[1])**2)
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
                fallback_raw_cx = raw_cx if raw_cx != 0 else sw/2
                fallback_raw_cy = raw_cy if raw_cy != 0 else sl/2
                wwt_pt = min(wwt_corners, key=lambda c: (c[0]-fallback_raw_cx)**2 + (c[1]-fallback_raw_cy)**2)
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
        if wwt_pt:
            water_triangle.append(wwt_pt)

        return [], candidate_points, active_cases, water_triangle

    pb_rect = rack_buffers["Power Block"][active_cases["Power Block"]]
    ct_rect = rack_buffers["Cooling Tower"][active_cases["Cooling Tower"]]

    # B-1 step 1-2 — choose PB and CT spine sides JOINTLY (see §3.6.B).
    # The old logic picked each side independently by "which side faces RAW",
    # which often selected sides that don't face each other and forced the A*
    # connector to wrap around, producing very long spines. Instead, score every
    # (pb_side, ct_side) pair by the PB<->CT connection gap (dominant, == the
    # thing that blows up) plus a small "PB side faces RAW" term (keeps the
    # downstream water connection short, since pb_spine_mid ranks RAW corners).
    def rect_sides(rect):
        x, y, w, h = rect
        return [
            [(x, y), (x + w, y)],            # bottom (low y)
            [(x, y + h), (x + w, y + h)],    # top
            [(x, y), (x, y + h)],            # left
            [(x + w, y), (x + w, y + h)],    # right
        ]

    def side_inside_plot(side):
        (ax, ay), (bx, by) = side
        return (0 <= min(ax, bx) and max(ax, bx) <= sw and
                0 <= min(ay, by) and max(ay, by) <= sl)

    def side_gap(side_a, side_b):
        # L1 (Manhattan) distance between two axis-aligned segments: the
        # perpendicular separation plus any lateral offset where their
        # projections don't overlap. Small when the sides face each other.
        (ax0, ay0), (ax1, ay1) = side_a
        (bx0, by0), (bx1, by1) = side_b
        ax_lo, ax_hi = min(ax0, ax1), max(ax0, ax1)
        ay_lo, ay_hi = min(ay0, ay1), max(ay0, ay1)
        bx_lo, bx_hi = min(bx0, bx1), max(bx0, bx1)
        by_lo, by_hi = min(by0, by1), max(by0, by1)
        gap_x = max(0.0, ax_lo - bx_hi, bx_lo - ax_hi)
        gap_y = max(0.0, ay_lo - by_hi, by_lo - ay_hi)
        return gap_x + gap_y

    def side_mid(side):
        (ax, ay), (bx, by) = side
        return ((ax + bx) / 2.0, (ay + by) / 2.0)

    def side_faces(side, block_cx, block_cy, tx, ty):
        # True if the target point (tx, ty) lies on the OUTWARD side of `side`
        # (the half-plane away from the block's own center). A side that faces
        # the other block lets the connection run straight out toward it; a side
        # facing away forces a U-shaped wrap.
        (ax, ay), (bx, by) = side
        if abs(ay - by) < 0.1:                       # horizontal side: normal is y
            return (ty - ay) * (ay - block_cy) > 0.1
        return (tx - ax) * (ax - block_cx) > 0.1     # vertical side: normal is x

    pb_sides = [s for s in rect_sides(pb_rect) if side_inside_plot(s)] or rect_sides(pb_rect)
    ct_sides = [s for s in rect_sides(ct_rect) if side_inside_plot(s)] or rect_sides(ct_rect)

    # Prefer pairs where BOTH sides face each other (clean straight/L connection,
    # no wrap). Only if no such pair exists do we fall back to all combinations.
    facing_pairs = [
        (pb_s, ct_s)
        for pb_s in pb_sides for ct_s in ct_sides
        if side_faces(pb_s, pb_cx, pb_cy, ct_cx, ct_cy)
        and side_faces(ct_s, ct_cx, ct_cy, pb_cx, pb_cy)
    ]
    candidate_pairs = facing_pairs or [
        (pb_s, ct_s) for pb_s in pb_sides for ct_s in ct_sides
    ]

    best_pb_side, best_ct_side = candidate_pairs[0]
    best_cost = float('inf')
    for pb_s, ct_s in candidate_pairs:
        pmx, pmy = side_mid(pb_s)
        raw_pen = ((pmx - raw_cx) ** 2 + (pmy - raw_cy) ** 2) ** 0.5
        cost = side_gap(pb_s, ct_s) + SPINE_RAW_WEIGHT * raw_pen
        if cost < best_cost:
            best_cost = cost
            best_pb_side, best_ct_side = pb_s, ct_s

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
                if ox0 - 0.1 <= pb_cx <= ox1 + 0.1:
                    x_mid = pb_cx
                else:
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
                if oy0 - 0.1 <= pb_cy <= oy1 + 0.1:
                    y_mid = pb_cy
                else:
                    y_mid = (oy0 + oy1) / 2
                return [(x_seg, y_mid), (x_tgt, y_mid)]
            else:
                if seg_y1 < tgt_y0:
                    return [(x_seg, seg_y1), (x_tgt, tgt_y0)]
                else:
                    return [(x_seg, seg_y0), (x_tgt, tgt_y1)]

    pb_halves = split_segment(best_pb_side)
    ct_halves = split_segment(best_ct_side)

    is_overlap = segments_overlap(best_pb_side, best_ct_side)
    is_pb_horiz = abs(best_pb_side[0][1] - best_pb_side[1][1]) < 0.1

    best_pair = None
    min_d = float('inf')
    for pb_h in pb_halves:
        for ct_h in ct_halves:
            d = dist_sq(pb_h, ct_h)
            if is_overlap:
                if is_pb_horiz:
                    # Horizontal sides overlap: prioritize ct_h covering pb_cx
                    ct_x0 = min(ct_h[0][0], ct_h[1][0])
                    ct_x1 = max(ct_h[0][0], ct_h[1][0])
                    if ct_x0 - 0.1 <= pb_cx <= ct_x1 + 0.1:
                        d -= 1000000.0
                else:
                    # Vertical sides overlap: prioritize ct_h covering pb_cy
                    ct_y0 = min(ct_h[0][1], ct_h[1][1])
                    ct_y1 = max(ct_h[0][1], ct_h[1][1])
                    if ct_y0 - 0.1 <= pb_cy <= ct_y1 + 0.1:
                        d -= 1000000.0

            if d < min_d:
                min_d = d
                best_pair = (pb_h, ct_h)

    best_pb_half, best_ct_half = best_pair

    # Under overlap exception:
    pb_case = active_cases["Power Block"]
    ct_case = active_cases["Cooling Tower"]

    p1a, p1b = best_pb_side
    p2a, p2b = best_ct_side
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
    overlap_connector = None   # straight overlap bridge, candidate for A* reroute

    if is_overlap and pb_case == "case1_rack" and ct_case == "case2_rack":
        # One straight perpendicular spine on the MAIN RACK axis (through PB
        # center), from the PB center to CT's CASE 1 rack-buffer line. Split at
        # the overlapped PB/CT side: PB center -> overlap is the MAIN RACK; the
        # overlap -> CT case1 part is the CT connector. Kept as two segments
        # (the main rack takes a different width later). Replaces the step-5
        # MAIN RACK (so it is not drawn again below).
        ct1 = rack_buffers["Cooling Tower"]["case1_rack"]
        cx1, cy1, cw1, ch1 = ct1
        if is_pb_horiz:
            overlap_y = best_pb_half[0][1]
            ct1_y = (cy1 + ch1) if best_ct_side[0][1] > ct_cy else cy1
            main_rack = [(pb_cx, pb_cy), (pb_cx, overlap_y)]
            perp_line = [(pb_cx, overlap_y), (pb_cx, ct1_y)]
        else:
            overlap_x = best_pb_half[0][0]
            ct1_x = (cx1 + cw1) if best_ct_side[0][0] > ct_cx else cx1
            main_rack = [(pb_cx, pb_cy), (overlap_x, pb_cy)]
            perp_line = [(overlap_x, pb_cy), (ct1_x, pb_cy)]
        spine_centerlines.append(perp_line)
        spine_centerlines.append(main_rack)
        spine_creation_debug["perp_line"] = perp_line
        spine_creation_debug["main_rack"] = main_rack
        overlap_connector = perp_line
    elif is_overlap and pb_case == "case2_rack" and ct_case == "case1_rack":
        # Mirror of the case1/case2 rule. Here PB is case2 (its active side sits
        # FAR from PB) and CT is case1 (active side close to CT), so the gap to
        # bridge is on the PB side -- the main-rack axis line traverses it. A
        # single straight perpendicular line on the MAIN RACK axis runs from the
        # PB center to CT's case1 rack buffer (the overlapped CT side); its far
        # ("start") point lands ON the CT rack buffer. No separate CT connector.
        if is_pb_horiz:
            ct_buffer_y = best_ct_side[0][1]
            overlap_y = best_pb_half[0][1]
            main_rack = [(pb_cx, pb_cy), (pb_cx, overlap_y)]
            perp_line = [(pb_cx, overlap_y), (pb_cx, ct_buffer_y)]
        else:
            ct_buffer_x = best_ct_side[0][0]
            overlap_x = best_pb_half[0][0]
            main_rack = [(pb_cx, pb_cy), (overlap_x, pb_cy)]
            perp_line = [(overlap_x, pb_cy), (ct_buffer_x, pb_cy)]
        spine_centerlines.append(perp_line)
        spine_centerlines.append(main_rack)
        spine_creation_debug["perp_line"] = perp_line
        spine_creation_debug["main_rack"] = main_rack
        overlap_connector = perp_line
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

        # Same-case overlap (PB and CT sides overlap but share a case): the A*
        # connect below is gated on `not is_overlap`, so it would leave the CT
        # half disconnected. The two halves are parallel and overlap in
        # projection, so bridge them with a single perpendicular connector.
        if is_overlap:
            connector = closest_perp_line(best_pb_half, best_ct_half)
            spine_centerlines.append(connector)
            spine_creation_debug["perp_line"] = connector
            overlap_connector = connector

    # 7b. Reroute an overlap connector that slices through a block. The overlap
    # straight bridge (closest_perp_line) has NO obstacle avoidance, so it can cut
    # through an intervening block (e.g. Warehouse between PB and CT). If it does,
    # drop it and let the step-7 A* rebuild the connection around every block's
    # Case 1 rack buffer.
    other_blocks = [b for b in blocks if b["name"] not in ("Power Block", "Cooling Tower")]

    def _seg_hits_blocks(seg):
        for b in other_blocks:
            if b["name"] == "Gate House":
                rect = (b["x"], b["y"], b["width"], b["height"])
            else:
                rect = rack_buffers[b["name"]]["case1_rack"]
            if line_intersects_pb(seg[0], seg[1], rect):
                return True
        return False

    overlap_reroute = False
    if is_overlap and overlap_connector is not None and _seg_hits_blocks(overlap_connector):
        overlap_reroute = True
        spine_centerlines = [s for s in spine_centerlines if s is not overlap_connector]
        spine_creation_debug["perp_line"] = None
        spine_creation_debug["overlap_reroute"] = True

    # 7. Connect PB and CT centerlines (Step B-1 rule 7)
    _n_spine_before_astar = len(spine_centerlines)
    if (not is_overlap) or overlap_reroute:
        grid_b1 = Grid(sw, sl, cell_size=CELL_SIZE)
        grid_b2 = Grid(sw, sl, cell_size=CELL_SIZE)

        def mark_b1_grids(inflate):
            # inflate=True forces paths onto the rack-buffer line (point 3);
            # the footprint-only fallback (inflate=False) is used if routing
            # fails under the tighter inflated obstacles.
            grid_b1.blocked[:, :] = False
            grid_b2.blocked[:, :] = False
            if inflate:
                # Floor every block at its Case 1 rack buffer so the PB↔CT spine
                # routes around each block's minimum rack zone, not just its
                # footprint (point: "almost every block has a min rack buffer").
                min_buf = max(0.0, RACK_CASE1_OFFSET - CELL_SIZE)
                mark_rack_obstacles(grid_b1, blocks, rack_buffers, active_cases,
                                    min_inflate=min_buf)
                mark_rack_obstacles(grid_b2, blocks, rack_buffers, active_cases,
                                    exclude={"Power Block"}, min_inflate=min_buf)
            else:
                for b in blocks:
                    grid_b1.mark_building(b, inflate_m=0)
                    if b["name"] != "Power Block":
                        grid_b2.mark_building(b, inflate_m=0)
            # Re-apply the polygon mask AFTER the reset above (the reset wipes it).
            _mask_grid_to_plot(grid_b1, plot)
            _mask_grid_to_plot(grid_b2, plot)

        mark_b1_grids(inflate=True)

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

        start_cells_1 = get_seg_cells(best_pb_half)
        goal_cells_1 = set(get_seg_cells(best_ct_half))
        start_cells_2 = get_seg_cells(main_rack)
        goal_cells_2 = set(get_seg_cells(best_ct_half))

        def run_b1_searches():
            # Search 1: Spine-to-Spine (Power Block footprint is BLOCKED)
            for c in start_cells_1:
                grid_b1.blocked[c] = False
            for c in goal_cells_1:
                grid_b1.blocked[c] = False
            p1 = astar(
                grid_b1, start_cells_1, goal_cells_1,
                turn_penalty=10.0, width_cells=0, allow_diagonal=False,
                forbid_move=forbid_move_hook
            )
            # Search 2: Main Rack-to-Spine (Power Block footprint is NOT BLOCKED)
            for c in start_cells_2:
                grid_b2.blocked[c] = False
            for c in goal_cells_2:
                grid_b2.blocked[c] = False
            p2 = astar(
                grid_b2, start_cells_2, goal_cells_2,
                turn_penalty=10.0, width_cells=0, allow_diagonal=False,
                forbid_move=forbid_move_hook
            )
            return p1, p2

        path_1, path_2 = run_b1_searches()
        # Fallback: if the inflated buffer-corridor grid blocked all routes,
        # retry on the footprint-only grid.
        if not path_1 and not path_2:
            mark_b1_grids(inflate=False)
            path_1, path_2 = run_b1_searches()

        dist_1 = (len(path_1) - 1) * CELL_SIZE if path_1 else float('inf')
        dist_2 = (len(path_2) - 1) * CELL_SIZE if path_2 else float('inf')

        # Compare and pick the shorter connection path (original Layout06 0626 rule).
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
            # Also snap to the existing spine endpoints (PB/CT halves, MAIN RACK)
            # so the A* connector meets them exactly instead of landing one grid
            # cell off (e.g. y=185 vs a half-line at y=184).
            for seg in spine_centerlines:
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

    # Safety: if an overlap reroute found NO A* path, the connection would be
    # left open — restore the straight connector so PB/CT stay linked.
    if overlap_reroute and len(spine_centerlines) == _n_spine_before_astar and overlap_connector is not None:
        spine_centerlines.append(overlap_connector)
        spine_creation_debug["perp_line"] = overlap_connector
        spine_creation_debug["overlap_reroute"] = "failed-restored"

    spine_creation_debug["spine_centerlines"] = spine_centerlines

    # B-1 step 7b — intersection of the PB↔CT spine with the PB CASE 1 rack
    # buffer. After the spine network is connected (step 7), find where it
    # crosses the PB case1 rack-buffer rectangle boundary. If the active PB side
    # is the case1 side it lies ON that edge (collinear → skipped); otherwise the
    # MAIN RACK stub / connector crosses the case1 buffer where it passes through.
    def _seg_seg_intersect(a, b, c, d):
        (x1, y1), (x2, y2) = a, b
        (x3, y3), (x4, y4) = c, d
        den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(den) < 1e-9:
            return None  # parallel or collinear (e.g. the PB half on the edge)
        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
        u = ((x1 - x3) * (y1 - y2) - (y1 - y3) * (x1 - x2)) / den
        if -1e-6 <= t <= 1 + 1e-6 and -1e-6 <= u <= 1 + 1e-6:
            return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
        return None

    pb_case1_rect = rack_buffers["Power Block"]["case1_rack"]
    bx0, by0, bw0, bh0 = pb_case1_rect
    pb_buffer_edges = [
        [(bx0, by0), (bx0 + bw0, by0)],
        [(bx0 + bw0, by0), (bx0 + bw0, by0 + bh0)],
        [(bx0 + bw0, by0 + bh0), (bx0, by0 + bh0)],
        [(bx0, by0 + bh0), (bx0, by0)],
    ]
    pb_buffer_hits = []
    for seg in spine_centerlines:
        for e in pb_buffer_edges:
            ip = _seg_seg_intersect(seg[0], seg[1], e[0], e[1])
            if ip is not None and not any(
                abs(ip[0] - q[0]) < 0.5 and abs(ip[1] - q[1]) < 0.5 for q in pb_buffer_hits
            ):
                pb_buffer_hits.append(ip)
    spine_creation_debug["pb_buffer_hits"] = pb_buffer_hits

    # B-1 step 7c — CUT the spine at the case1 buffer to split MAIN RACK from the
    # PB↔CT spine. The MAIN RACK axis runs PB-centre -> active rack buffer; cut it
    # where it crosses the case1 (6 m) buffer:
    #   * PB-centre -> cut point  = MAIN RACK OUTPUT (the spine "inside" the PB).
    #   * cut point  -> rest      = part of the PB↔CT spine.
    # Geometry/connectivity are unchanged — we only add a vertex at the cut and
    # tag the inner part. The PB↔CT connection itself still uses the 0626 A* logic
    # built above. If the active case already IS case1 the cut lands on the rack
    # end (degenerate leftover) and MAIN RACK == the whole stub.
    main_rack_output = main_rack
    cut_pt = None
    for e in pb_buffer_edges:
        ip = _seg_seg_intersect(main_rack[0], main_rack[1], e[0], e[1])
        if ip is not None:
            cut_pt = ip
            break
    if cut_pt is not None:
        pbc, far = main_rack[0], main_rack[1]
        d_near = abs(cut_pt[0] - pbc[0]) + abs(cut_pt[1] - pbc[1])
        d_far = abs(cut_pt[0] - far[0]) + abs(cut_pt[1] - far[1])
        main_rack_output = [pbc, cut_pt]
        if d_near > 0.5 and d_far > 0.5:
            # Active case is case2: replace the full stub with [inner, leftover]
            # so the spine keeps a vertex at the cut (both parts stay drawn).
            spine_centerlines = [s for s in spine_centerlines if s is not main_rack]
            spine_centerlines.append([cut_pt, far])
            spine_centerlines.append(main_rack_output)
    spine_creation_debug["main_rack_output"] = main_rack_output
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

        is_wwt_split = False
        pb_block = next((b for b in blocks if b["name"] == "Power Block"), None)
        if pb_block and wwt_pt and kept_source:
            pb_rect = (pb_block["x"], pb_block["y"], pb_block["width"], pb_block["height"])
            if line_intersects_pb(kept_source, wwt_pt, pb_rect):
                is_wwt_split = True

    water_triangle = []
    if kept_raw: water_triangle.append(kept_raw)
    if kept_demi: water_triangle.append(kept_demi)
    if wwt_pt and not is_wwt_split:
        water_triangle.append(wwt_pt)

    return spine_centerlines, candidate_points, active_cases, water_triangle, pb_buffer_hits, main_rack_output


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

def generate_group_a_access(computed_buffers, placed, site_w, site_l, gate_cx, gate_cy):
    return []

def point_to_segment_distance(p, a, b):
    px, py = p
    ax, ay = a
    bx, by = b
    dx = bx - ax
    dy = by - ay
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx*dx + dy*dy)
    t = max(0.0, min(1.0, t))
    proj_x = ax + t * dx
    proj_y = ay + t * dy
    return math.hypot(px - proj_x, py - proj_y)

def find_closest_point_on_road(p_buf, road_segments):
    min_d = float('inf')
    closest_pt = p_buf
    for seg in road_segments:
        a, b = seg
        px, py = p_buf
        ax, ay = a
        bx, by = b
        dx = bx - ax
        dy = by - ay
        if abs(dx) < 1e-6 and abs(dy) < 1e-6:
            d = math.hypot(px - ax, py - ay)
            pt = a
        else:
            t = ((px - ax) * dx + (py - ay) * dy) / (dx*dx + dy*dy)
            t = max(0.0, min(1.0, t))
            pt = (ax + t * dx, ay + t * dy)
            d = math.hypot(px - pt[0], py - pt[1])
        if d < min_d:
            min_d = d
            closest_pt = pt
    return closest_pt

def unblock_segments_on_grid(grid, segments):
    for seg in segments:
        p1, p2 = seg
        x1, y1 = p1
        x2, y2 = p2
        dist = math.hypot(x2 - x1, y2 - y1)
        if dist < 0.1:
            i, j = grid.world_to_cell(x1, y1)
            if grid.in_bounds(i, j):
                grid.blocked[i, j] = False
            continue
        steps = int(math.ceil(dist / (grid.cell_size / 2)))
        for s in range(steps + 1):
            t = s / steps
            cx = x1 + t * (x2 - x1)
            cy = y1 + t * (y2 - y1)
            i, j = grid.world_to_cell(cx, cy)
            if grid.in_bounds(i, j):
                grid.blocked[i, j] = False

def is_path_clear(grid, path):
    for i in range(len(path) - 1):
        p1, p2 = path[i], path[i+1]
        x1, y1 = p1
        x2, y2 = p2
        dist = math.hypot(x2 - x1, y2 - y1)
        if dist < 0.1:
            continue
        steps = int(math.ceil(dist / (grid.cell_size / 2)))
        for s in range(steps + 1):
            t = s / steps
            cx = x1 + t * (x2 - x1)
            cy = y1 + t * (y2 - y1)
            ci, cj = grid.world_to_cell(cx, cy)
            if not grid.is_free(ci, cj):
                return False
    return True

def is_path_clear_of_buffers(grid, path, penalty_map):
    if not is_path_clear(grid, path):
        return False
    for i in range(len(path) - 1):
        p1, p2 = path[i], path[i+1]
        x1, y1 = p1
        x2, y2 = p2
        dist = math.hypot(x2 - x1, y2 - y1)
        if dist < 0.1:
            continue
        steps = int(math.ceil(dist / (grid.cell_size / 2)))
        for s in range(steps + 1):
            t = s / steps
            cx = x1 + t * (x2 - x1)
            cy = y1 + t * (y2 - y1)
            ci, cj = grid.world_to_cell(cx, cy)
            if grid.in_bounds(ci, cj) and penalty_map[ci, cj] > 0.0:
                return False
    return True

def get_side_buffer_offset(block, side_midpoint, rack_segments):
    if block["name"] not in RACK_BLOCKS:
        return 8.0
    for seg in rack_segments:
        if point_to_segment_distance(side_midpoint, seg[0], seg[1]) < 25.0:
            return 16.0
    return 8.0

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
def build_pb_ring_road(pb_x, pb_y, pb_w, pb_h, offset=PB_RING_OFFSET):
    """Closed polyline of PB ring road centerline."""
    x1, y1 = pb_x - offset, pb_y - offset
    x2, y2 = pb_x + pb_w + offset, pb_y + pb_h + offset
    return [(x1,y1),(x2,y1),(x2,y2),(x1,y2),(x1,y1)]

def cleanup_parallel_segments(segs, sw, sl, computed_buffers, ref_segs=None, tol=17.0, gdz=None, pb_cx=0):
    return []

def generate_sketch(  # → §3.1 Master Placement Sequence
    site_w, site_l, wind_dir,
    gate_side="N", gate_ratio=0.5,
    gh_edge="N",    gh_ratio=0.5,  gh_offset=0,
    bb_edge="S",
    gis_edge="N",   gis_ratio=0.8, gis_offset=0,
    water_edge="E", water_ratio=0.2, water_offset=0,
    max_pool=300,
    plot=None, dxf_anchors=None, dxf_gate=None, dxf_boom=None, blocks_only=False,
    time_budget=25.0,
):
    """Polygon migration parameters (all optional; None/False = legacy rectangle):
      plot         : Core.Plot.Plot — the convex plot polygon. When given, site_w
                     / site_l are taken from its bounding box and all containment
                     checks run against the polygon (incl. diagonal sides).
      dxf_anchors  : {"Gate House"/"GIS"/"RAW Water Tank": (x, y, w, h)} read from
                     CAD. Placed at these positions each attempt, with the same
                     per-attempt jitter as the legacy anchors (GH/RAW ±5%, GIS 0).
      dxf_gate     : (x, y) gate point on the boundary (from the Gate circle).
      dxf_boom     : [(x1, y1), (x2, y2)] boom barrier line (from CAD).
      blocks_only  : stop after block placement (Power Block + anchors + floated)
                     and return a partial result — skips spurs/racks/perimeter,
                     which are not polygon-ready yet (later migration phases)."""
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
    if plot is not None:
        # The plot is origin-normalised, so its bounding box is (0, 0, sw, sl).
        sw, sl = plot.size
    if dxf_gate is not None:
        gate_pt = dxf_gate
        # Derive an approximate N/S/E/W "gate side" from the gate edge's outward
        # normal — used by the PB clamp / leeward logic. (The spur stage that
        # truly needs it is skipped in blocks_only mode.)
        ge = plot.nearest_edge(*gate_pt) if plot is not None else None
        if ge is not None:
            nx, ny = plot.edges[ge]["normal"]
            gate_side = ("E" if -nx > 0 else "W") if abs(nx) >= abs(ny) else ("N" if -ny > 0 else "S")
    else:
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

    # Wall-clock safety cap: no seed may run forever. If the budget is exceeded
    # we stop trying and return None (a "no-fit" result) instead of spinning —
    # this is what prevents a hung/looping seed from pinning a CPU core.
    global _t_start, _time_budget
    _t_start = time.time()
    _time_budget = time_budget

    for _attempt in range(max_pool * len(_PASS_TOLS)):
        if _time_budget and (time.time() - _t_start) > _time_budget:
            _last_debug["timed_out"] = True
            _last_debug["failed_section"] = f"time budget {_time_budget:.0f}s exceeded"
            break
        _pass_tol, _pass_label = _PASS_TOLS[_attempt // max_pool]
        _last_debug["total_attempts"] += 1
        _last_debug["boundary_pass_label"] = _pass_label

        placed = {}   # name → (x, y, w, h)

        # 1. Fixed anchors  [→ §3.2] — jitter per block: ONLY RAW Water Tank moves
        # (±5% of the site). Gate House is fixed (its boom barrier is attached to
        # it) and GIS is fixed.
        boom_out = list(dxf_boom) if dxf_boom else []
        if dxf_anchors is not None:
            # Polygon mode: anchors come from CAD at absolute positions; keep RAW's
            # jitter around its CAD position and keep it inside the plot polygon.
            for name in ("Gate House", "GIS", "RAW Water Tank"):
                if name not in dxf_anchors:
                    continue
                bx, by, w, h = dxf_anchors[name]
                j = 0.05 if name == "RAW Water Tank" else 0.0
                placed_xy = (bx, by)
                if j:
                    for _ in range(20):  # try a few jittered spots, keep one inside
                        jx = snap(bx + random.uniform(-sw * j, sw * j))
                        jy = snap(by + random.uniform(-sl * j, sl * j))
                        if plot is None or plot.contains_rect(jx, jy, w, h, tol=_pass_tol):
                            placed_xy = (jx, jy)
                            break
                placed[name] = (snap(placed_xy[0]), snap(placed_xy[1]), w, h)
            # Gate House is fixed, so the boom barrier (attached to it) stays at its
            # CAD position — no offset needed.
        else:
            for name, edge, ratio, off in [
                ("Gate House",     gh_edge,    gh_ratio,    gh_offset),
                ("GIS",            gis_edge,   gis_ratio,   gis_offset),
                ("RAW Water Tank", water_edge, water_ratio, water_offset),
            ]:
                j = 0.05 if name == "RAW Water Tank" else 0.0
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

            # Base center: plot polygon center when given, else rectangle center.
            if plot is not None:
                pcx, pcy = plot.centroid
                cx = pcx - pw / 2 + dx
                cy = pcy - ph / 2 + dy
            else:
                cx = (sw - pw) / 2 + dx
                cy = (sl - ph) / 2 + dy
            return (max(pb_x_bounds[0], min(cx, pb_x_bounds[1])),
                    max(pb_y_bounds[0], min(cy, pb_y_bounds[1])))
        pb_result = _try_place(sw, sl, "Power Block", placed, _pb_sample, max_attempts=100,
                               buffer=pb_buf, x_bounds=tuple(pb_x_bounds), y_bounds=tuple(pb_y_bounds),
                               plot=plot, plot_tol=_pass_tol)
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
        gate_spur = []
        ring_spur = []
        gate_death_zone = None
        gate_road_out = []   # immutable snapshot of the gate spur for the polygon output
        ring_spur_out = []   # immutable snapshot of the ring spur for the polygon output
        # Plot centre — replaces sw/2, sl/2 in the original tie-break so the
        # exit_helper choice works on a polygon. Identical to sw/2, sl/2 for a
        # rectangle, so the legacy path is unchanged.
        cen_x = plot.centroid[0] if plot is not None else sw / 2
        cen_y = plot.centroid[1] if plot is not None else sl / 2
        # Boom edge + midpoint: in polygon mode derive them from the CAD boom line
        # so the ORIGINAL gate-spur construction runs unchanged; otherwise use the
        # legacy bb_edge parameter with the computed 8 m-offset midpoint.
        bb_edge_eff = bb_edge
        bb_mid_dxf = None
        if blocks_only and boom_out and "Gate House" in placed:
            bb_edge_eff, bb_mid_dxf = _boom_edge_and_mid(boom_out, placed["Gate House"])

        if "Gate House" in placed:
            gh_x, gh_y, gh_w, gh_h = placed["Gate House"]
            cx, cy = gh_x + gh_w / 2, gh_y + gh_h / 2
            if bb_mid_dxf is not None:
                bb_mid = bb_mid_dxf
            elif bb_edge_eff == "N": bb_mid = (cx, gh_y + gh_h + 8)
            elif bb_edge_eff == "S": bb_mid = (cx, gh_y - 8)
            elif bb_edge_eff == "E": bb_mid = (gh_x + gh_w + 8, cy)
            elif bb_edge_eff == "W": bb_mid = (gh_x - 8, cy)

            if bb_edge_eff in ("N", "S"):
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
                    if abs(p1[0] - cen_x) < abs(p2[0] - cen_x):
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
                    if abs(p1[1] - cen_y) < abs(p2[1] - cen_y):
                        exit_helper, other_corner = p1, p2
                    else:
                        exit_helper, other_corner = p2, p1

        if bb_mid and exit_helper and other_corner:
            # Calculate Gate Death Zone  [→ §3.4.C] — legacy: only when gate & gate
            # house share an edge; polygon mode: always (gate reached across boom).
            if blocks_only or gate_side == gh_edge:
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
            if bb_edge_eff in ("N", "S"):
                opp_perp = (gh_y - 8) if bb_edge_eff == "N" else (gh_y + gh_h + 8)
                exit_helper_opp = (exit_helper[0], opp_perp)
            else:
                opp_perp = (gh_x - 8) if bb_edge_eff == "E" else (gh_x + gh_w + 8)
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

            # Reject the corner if it forces a 180° U-turn at exit_helper (the final
            # ring-spur segment must align with the first gate-spur segment).
            if bb_edge_eff in ("N", "S"):
                is_valid = (ehx - sx) * (bb_mid[0] - ehx) >= 0
            else:
                is_valid = (ehy - sy) * (bb_mid[1] - ehy) >= 0

            if is_valid:
                spur_start = closest_corner
                # Ring spur L-route (Option A): project spur_start onto exit_line
                if bb_edge_eff in ("N", "S"):
                    turn_pt = (sx, ehy)
                else:
                    turn_pt = (ehx, sy)
                ring_spur = [spur_start, turn_pt, exit_helper]
            else:
                # Route A would U-turn. Two fallbacks:
                #  (1) if exit_helper lies WITHIN the ring road's span on the spur
                #      axis, drop a straight spur onto the nearest ring edge (clean);
                #  (2) otherwise exit_helper is OUTSIDE the ring road — route an L
                #      from the closest ring CORNER with a perpendicular final
                #      approach, so the spur always starts on the ring road and never
                #      backtracks against the gate spur.
                if bb_edge_eff in ("N", "S"):
                    sy_proj = rymax if abs(ehy - rymax) < abs(ehy - rymin) else rymin
                    if rxmin <= ehx <= rxmax:
                        ring_spur = [(ehx, sy_proj), exit_helper]
                    else:
                        ring_spur = [closest_corner, (ehx, sy), exit_helper]
                else:
                    sx_proj = rxmax if abs(ehx - rxmax) < abs(ehx - rxmin) else rxmin
                    if rymin <= ehy <= rymax:
                        ring_spur = [(sx_proj, ehy), exit_helper]
                    else:
                        ring_spur = [closest_corner, (sx, ehy), exit_helper]

            # gate_spur — cross the boom at bb_mid, route to gate (perfect 90° crossing).
            if bb_edge_eff in ("N", "S"):
                gate_spur = [exit_helper, bb_mid, other_corner, (gate_pt[0], other_corner[1]), gate_pt]
            else:
                gate_spur = [exit_helper, bb_mid, other_corner, (other_corner[0], gate_pt[1]), gate_pt]
            # Snapshot for the polygon output (the rack stage may mutate the live lists).
            gate_road_out = list(gate_spur)
            ring_spur_out = list(ring_spur)
        elif not blocks_only:
            gate_death_zone = None
            gate_spur = build_gate_spur(sw, sl, gate_pt)
            ring_spur = build_ring_spur(sw, sl, ring_road, fixed_blocks_so_far, gate_pt)

        # Spur exclusion zones — added BEFORE floated blocks for both paths so the
        # floated blocks avoid the gate/ring spur corridors.
        for zone_name, line in (("_gate_spur_zone", gate_spur),
                                ("_ring_spur_zone", ring_spur)):
            for i, rect in enumerate(_spur_exclusion_rect(line, buffer=ROAD_BUFFER)):
                placed[f"{zone_name}_{i}"] = rect

        # 4. Floated blocks — magnet placement with zone rules.  [→ §3.5]
        gh_x, gh_y = placed["Gate House"][:2]
        admin_anchor = ((gh_x + pb_cx) / 2, (gh_y + pb_cy) / 2)
        raw_x, raw_y, raw_w, raw_h = placed["RAW Water Tank"]
        raw_cx, raw_cy = raw_x + raw_w/2, raw_y + raw_h/2

        if plot is not None:
            _cen_x, _cen_y = plot.centroid
            def leeward_filter(x, y, w, h):
                bx, by = x + w / 2, y + h / 2
                if wind_dir == "East": return bx <= _cen_x
                if wind_dir == "West": return bx >= _cen_x
                if wind_dir == "North": return by <= _cen_y
                return by >= _cen_y
        else:
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
            if name == "Flare" and plot is not None:
                # Polygon mode: place at the leeward polygon vertex (§3.5.C).
                pos = _place_flare_on_polygon(plot, placed, wind_dir, _pass_tol)
                if pos is None and _pass_tol < BOUNDARY_TOLERANCE:
                    pos = _place_flare_on_polygon(plot, placed, wind_dir, BOUNDARY_TOLERANCE)
            elif name == "Flare":
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
                                        magnet_target=m_target, boundary_tol=_pass_tol, plot=plot)
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

        # Polygon migration (Phase 3): blocks-only mode returns the placed blocks
        # on the real plot shape, skipping the not-yet-polygon-ready road/rack/
        # perimeter stages. This is what the "Generate Layouts" button uses today.
        # 4. RACK placement — comes AFTER floated blocks  [→ §3.6]
        # BEFORE perimeter/spurs/stubs (racks are more important than roads).
        # Step A: per-block buffer rectangles for Case 1 & Case 2 layouts.
        # Steps B-1..B-5 and C (spine + connector) — implemented.
        rack_buffers = compute_rack_buffers(blocks)
        spine_centerlines, candidate_points, active_cases, water_triangle, pb_buffer_hits, main_rack_output = build_rack_spines(rack_buffers, blocks, sw, sl, ring_road, gate_spur, ring_spur, plot=plot)
        pb_ct_segments = list(spine_centerlines)
        water_cluster_segments = []
        rack_segments = list(spine_centerlines)
        pruned_rack_segments = []

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
        if len(water_triangle) >= 2:
            # Inflated grid forces water paths onto the rack-buffer line
            # (point 3); footprint-only grid is the per-route fallback.
            grid_b5 = Grid(sw, sl, cell_size=CELL_SIZE)
            mark_rack_obstacles(grid_b5, blocks, rack_buffers, active_cases)
            _mask_grid_to_plot(grid_b5, plot)
            grid_b5_full = Grid(sw, sl, cell_size=CELL_SIZE)
            for b in blocks:
                grid_b5_full.mark_building(b, inflate_m=0)
            _mask_grid_to_plot(grid_b5_full, plot)

            def astar_route_on(grid, p1, p2):
                c1 = grid.world_to_cell(*p1)
                c2 = grid.world_to_cell(*p2)
                was1 = grid.blocked[c1]
                was2 = grid.blocked[c2]
                grid.blocked[c1] = False
                grid.blocked[c2] = False
                path = astar(grid, c1, c2, width_cells=0, allow_diagonal=False,
                             turn_penalty=10.0)
                grid.blocked[c1] = was1
                grid.blocked[c2] = was2
                return [snap_pt(*grid.cell_to_world(*c)) for c in path] if path else []

            def astar_route(p1, p2):
                path = astar_route_on(grid_b5, p1, p2)
                return path if path else astar_route_on(grid_b5_full, p1, p2)
                
            if len(water_triangle) == 3:
                raw_pt, demi_pt, wwt_pt = water_triangle[0], water_triangle[1], water_triangle[2]
                
                path_rd = astar_route(raw_pt, demi_pt)
                path_rw = astar_route(raw_pt, wwt_pt)
                path_dw = astar_route(demi_pt, wwt_pt)
                
                len_rd = len(path_rd) if path_rd else float('inf')
                len_rw = len(path_rw) if path_rw else float('inf')
                len_dw = len(path_dw) if path_dw else float('inf')
                
                paths = [(len_rd, path_rd), (len_rw, path_rw), (len_dw, path_dw)]
                paths.sort(key=lambda x: x[0])
                
                chosen_paths = paths[:2]
            else:
                pt1, pt2 = water_triangle[0], water_triangle[1]
                path_12 = astar_route(pt1, pt2)
                len_12 = len(path_12) if path_12 else float('inf')
                chosen_paths = [(len_12, path_12)]
            
            for length, path in chosen_paths:
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
        if water_cluster_segments:
            pb_line = [spine_centerlines[0]] if len(spine_centerlines) >= 1 else []
            ct_line = [spine_centerlines[1]] if len(spine_centerlines) >= 2 else []
            grid_c = Grid(sw, sl, cell_size=CELL_SIZE)
            _mask_grid_to_plot(grid_c, plot)

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

            def route_between(source_segments, target_segments, prefer_geometric=False):
                def run_routing(restricted, inflate=True):
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
                        for b in blocks:
                            grid_c.mark_building(b, inflate_m=0)
                    else:
                        grid_c.blocked[:, :] = False
                        if inflate:
                            # Buffer-corridor full grid: keep the path on rack-buffer
                            # lines instead of grazing the footprint→buffer gap.
                            mark_rack_obstacles(grid_c, blocks, rack_buffers, active_cases)
                        else:
                            for b in blocks:
                                grid_c.mark_building(b, inflate_m=0)

                    # Unblock the main rack corridor inside the Power Block footprint
                    pb_block = next((b for b in blocks if b["name"] == "Power Block"), None)
                    if pb_block:
                        pb_x0 = pb_block["x"]
                        pb_x1 = pb_block["x"] + pb_block["width"]
                        pb_y0 = pb_block["y"]
                        pb_y1 = pb_block["y"] + pb_block["height"]
                        
                        # Find the main rack segment starting/ending at (pb_cx, pb_cy)
                        main_rack_seg = None
                        for seg in spine_centerlines:
                            p1, p2 = seg
                            if math.hypot(p1[0] - pb_cx, p1[1] - pb_cy) < 0.1 or math.hypot(p2[0] - pb_cx, p2[1] - pb_cy) < 0.1:
                                main_rack_seg = seg
                                break
                        
                        if main_rack_seg:
                            is_horiz = abs(main_rack_seg[0][1] - main_rack_seg[1][1]) < 0.1
                            if is_horiz:
                                c_y = grid_c.world_to_cell(pb_cx, pb_cy)[1]
                                c_x0 = max(0, int(math.floor(pb_x0 / CELL_SIZE)))
                                c_x1 = min(grid_c.ncols, int(math.ceil(pb_x1 / CELL_SIZE)))
                                grid_c.blocked[c_x0:c_x1, c_y:c_y+1] = False
                            else:
                                c_x = grid_c.world_to_cell(pb_cx, pb_cy)[0]
                                c_y0 = max(0, int(math.floor(pb_y0 / CELL_SIZE)))
                                c_y1 = min(grid_c.nrows, int(math.ceil(pb_y1 / CELL_SIZE)))
                                grid_c.blocked[c_x:c_x+1, c_y0:c_y1] = False

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

                    # Build list of road cells to penalize crossing roads
                    road_cells = set()
                    for seg in road_segs:
                        c1 = grid_c.world_to_cell(*seg[0])
                        c2 = grid_c.world_to_cell(*seg[1])
                        if c1[0] == c2[0]: # Vertical
                            for y in range(min(c1[1], c2[1]), max(c1[1], c2[1]) + 1):
                                road_cells.add((c1[0], y))
                        elif c1[1] == c2[1]: # Horizontal
                            for x in range(min(c1[0], c2[0]), max(c1[0], c2[0]) + 1):
                                road_cells.add((x, c1[1]))

                    def road_crossing_cost(from_cell, to_cell):
                        if to_cell in road_cells:
                            return 100.0 / CELL_SIZE
                        return 0.0

                    path = astar(
                        grid_c,
                        start_cells,
                        goal_cells,
                        turn_penalty=10.0,
                        width_cells=0,
                        allow_diagonal=False,
                        forbid_move=forbid_move_hook,
                        cell_cost_fn=road_crossing_cost
                    )
                    return path

                if prefer_geometric:
                    # Skip the extended-line restricted grid (it spans each
                    # spine/water segment across the whole site, pulling the
                    # connection to a non-nearest point) and route on the true
                    # geometric grid so the link attaches at the closest point.
                    path = run_routing(restricted=False, inflate=True)
                    if not path:
                        path = run_routing(restricted=False, inflate=False)
                    if not path:
                        path = run_routing(restricted=True)
                else:
                    path = run_routing(restricted=True)
                    if not path:
                        path = run_routing(restricted=False, inflate=True)
                    if not path:
                        path = run_routing(restricted=False, inflate=False)

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
                    
                    # Align new segments with existing target segments to avoid 1m jogs
                    for seg in new_segs:
                        p1, p2 = seg
                        is_horiz = abs(p1[1] - p2[1]) < 0.1
                        if is_horiz:
                            for eseg in target_segments:
                                ep1, ep2 = eseg
                                if abs(ep1[1] - ep2[1]) < 0.1: # horizontal
                                    if abs(p1[1] - ep1[1]) <= 3.0:
                                        p1 = (p1[0], ep1[1])
                                        p2 = (p2[0], ep1[1])
                                        seg[0] = p1
                                        seg[1] = p2
                                        break
                        else:
                            for eseg in target_segments:
                                ep1, ep2 = eseg
                                if abs(ep1[0] - ep2[0]) < 0.1: # vertical
                                    if abs(p1[0] - ep1[0]) <= 3.0:
                                        p1 = (ep1[0], p1[1])
                                        p2 = (ep1[0], p2[1])
                                        seg[0] = p1
                                        seg[1] = p2
                                        break
                                        
                    return path[-1], new_segs
                return None, []

            # 1. PB/CT spine network to water cluster spine
            if spine_centerlines:
                found_goal_1, new_segs_1 = route_between(spine_centerlines, water_cluster_segments)
                water_cluster_segments.extend(new_segs_1)
            
            # WWT split connection stage
            if len(water_triangle) == 2:
                wwt_block = next((b for b in blocks if b["name"] == "WT/WWT"), None)
                if wwt_block:
                    wwt_rect = rack_buffers.get("WT/WWT", {}).get(active_cases.get("WT/WWT"))
                    if wwt_rect:
                        wx, wy, ww, wh = wwt_rect
                        wwt_boundary_segs = [
                            [(wx, wy), (wx+ww, wy)],
                            [(wx+ww, wy), (wx+ww, wy+wh)],
                            [(wx, wy+wh), (wx+ww, wy+wh)],
                            [(wx, wy), (wx, wy+wh)]
                        ]
                        target_segs = spine_centerlines if spine_centerlines else water_cluster_segments
                        best_pair = closest_points_between_networks(wwt_boundary_segs, target_segs)
                        if best_pair:
                            pt_wwt, pt_target = best_pair
                            # Align pt_wwt to pt_target in x or y if they are within 1 cell (2.0m)
                            aligned_x = pt_target[0] if abs(pt_wwt[0] - pt_target[0]) <= 2.1 else pt_wwt[0]
                            aligned_y = pt_target[1] if abs(pt_wwt[1] - pt_target[1]) <= 2.1 else pt_wwt[1]
                            pt_wwt_aligned = (aligned_x, aligned_y)
                            route_between([[pt_wwt_aligned, pt_wwt_aligned]], [[pt_target, pt_target]], prefer_geometric=True)

            # Simplify zigzags in the water cluster to make them L-shaped
            if water_cluster_segments:
                def simplify_zigzags(segments, blocks):
                    def hits_footprint(s):
                        for b in blocks:
                            bx, by, bw, bh = b["x"], b["y"], b["width"], b["height"]
                            if line_intersects_pb(s[0], s[1], (bx, by, bw, bh)):
                                return True
                        return False

                    changed = True
                    while changed:
                        if _time_budget and (time.time() - _t_start) > _time_budget:
                            break
                        changed = False
                        for i, seg1 in enumerate(segments):
                            for j, seg2 in enumerate(segments):
                                if i == j: continue
                                for k, seg3 in enumerate(segments):
                                    if k == i or k == j: continue
                                    
                                    # 1. Check V-H-V zigzag
                                    is_v1 = abs(seg1[0][0] - seg1[1][0]) < 0.1
                                    is_h = abs(seg2[0][1] - seg2[1][1]) < 0.1
                                    is_v2 = abs(seg3[0][0] - seg3[1][0]) < 0.1
                                    
                                    if is_v1 and is_h and is_v2:
                                        x1 = seg1[0][0]
                                        y1, y2 = min(seg1[0][1], seg1[1][1]), max(seg1[0][1], seg1[1][1])
                                        x_h_min, x_h_max = min(seg2[0][0], seg2[1][0]), max(seg2[0][0], seg2[1][0])
                                        y_h = seg2[0][1]
                                        y3_min, y3_max = min(seg3[0][1], seg3[1][1]), max(seg3[0][1], seg3[1][1])
                                        x3 = seg3[0][0]
                                        
                                        if (abs(y_h - y1) < 0.1 or abs(y_h - y2) < 0.1) and (abs(y_h - y3_min) < 0.1 or abs(y_h - y3_max) < 0.1):
                                            if abs(x_h_min - min(x1, x3)) < 0.1 and abs(x_h_max - max(x1, x3)) < 0.1:
                                                y_other = y1 if abs(y_h - y2) < 0.1 else y2
                                                v1_new = [(x3, y_other), (x3, y_h)]
                                                h_new = [(x1, y_other), (x3, y_other)]
                                                if not hits_footprint(v1_new) and not hits_footprint(h_new):
                                                    seg1[0], seg1[1] = v1_new[0], v1_new[1]
                                                    seg2[0], seg2[1] = h_new[0], h_new[1]
                                                    changed = True
                                                    break
                                    
                                    # 2. Check H-V-H zigzag
                                    is_h1 = abs(seg1[0][1] - seg1[1][1]) < 0.1
                                    is_v = abs(seg2[0][0] - seg2[1][0]) < 0.1
                                    is_h2 = abs(seg3[0][1] - seg3[1][1]) < 0.1
                                    
                                    if is_h1 and is_v and is_h2:
                                        y1 = seg1[0][1]
                                        x1, x2 = min(seg1[0][0], seg1[1][0]), max(seg1[0][0], seg1[1][0])
                                        y_v_min, y_v_max = min(seg2[0][1], seg2[1][1]), max(seg2[0][1], seg2[1][1])
                                        x_v = seg2[0][0]
                                        y3 = seg3[0][1]
                                        x3_min, x3_max = min(seg3[0][0], seg3[1][0]), max(seg3[0][0], seg3[1][0])
                                        
                                        if (abs(x_v - x1) < 0.1 or abs(x_v - x2) < 0.1) and (abs(x_v - x3_min) < 0.1 or abs(x_v - x3_max) < 0.1):
                                            if abs(y_v_min - min(y1, y3)) < 0.1 and abs(y_v_max - max(y1, y3)) < 0.1:
                                                x_other = x1 if abs(x_v - x2) < 0.1 else x2
                                                h1_new = [(x_other, y3), (x_v, y3)]
                                                v_new = [(x_other, y1), (x_other, y3)]
                                                if not hits_footprint(h1_new) and not hits_footprint(v_new):
                                                    seg1[0], seg1[1] = h1_new[0], h1_new[1]
                                                    seg2[0], seg2[1] = v_new[0], v_new[1]
                                                    changed = True
                                                    break
                                if changed: break
                            if changed: break

                simplify_zigzags(water_cluster_segments, blocks)

            # Step C-2: Flare Pipe Rack  [→ §3.6.C-2]
            flare_block = next((b for b in blocks if b["name"] == "Flare"), None)
            if flare_block:
                fx, fy, fw, fh = flare_block["x"], flare_block["y"], flare_block["width"], flare_block["height"]
                flare_offset = RACK_CASE1_OFFSET
                fx0, fy0 = fx - flare_offset, fy - flare_offset
                fx1, fy1 = fx + fw + flare_offset, fy + fh + flare_offset
                
                # Clamp to plot boundary to keep paths strictly within the plot
                fx0_clamped = max(0.0, min(sw, fx0))
                fx1_clamped = max(0.0, min(sw, fx1))
                fy0_clamped = max(0.0, min(sl, fy0))
                fy1_clamped = max(0.0, min(sl, fy1))
                
                def touches_flare(segments):
                    for p1, p2 in segments:
                        sxmin, sxmax = min(p1[0], p2[0]), max(p1[0], p2[0])
                        symin, symax = min(p1[1], p2[1]), max(p1[1], p2[1])
                        if sxmax < fx0_clamped or sxmin > fx1_clamped: continue
                        if symax < fy0_clamped or symin > fy1_clamped: continue
                        return True
                    return False

                if not touches_flare(rack_segments):
                    flare_boundary_segs = [
                        [(fx0_clamped, fy0_clamped), (fx1_clamped, fy0_clamped)], # Bottom
                        [(fx1_clamped, fy0_clamped), (fx1_clamped, fy1_clamped)], # Right
                        [(fx0_clamped, fy1_clamped), (fx1_clamped, fy1_clamped)], # Top
                        [(fx0_clamped, fy0_clamped), (fx0_clamped, fy1_clamped)]  # Left
                    ]
                    
                    # Target = the WHOLE rack network (spine + water cluster +
                    # connectors AND the main rack at the PB centre) so the Flare
                    # attaches to the NEAREST existing rack — no segments excluded.
                    target_segs = list(rack_segments or spine_centerlines or water_cluster_segments)
                            
                    route_between(flare_boundary_segs, target_segs, prefer_geometric=True)

                # Add to rack_buffers for dashboard visualization
                rack_buffers["Flare"] = {"case1_rack": (fx0, fy0, fw + 2 * flare_offset, fh + 2 * flare_offset)}

            # Step C-3: Clean up the rack network  [→ §3.6.C-3]
            pb_half = spine_centerlines[0] if len(spine_centerlines) >= 1 else None
            ct_half = spine_centerlines[1] if len(spine_centerlines) >= 2 else None

            # Build original graph to find and preserve critical PB-CT connection path
            pb_rect = rack_buffers.get("Power Block", {}).get(active_cases.get("Power Block"))
            ct_rect = rack_buffers.get("Cooling Tower", {}).get(active_cases.get("Cooling Tower"))
            
            orig_rack_segments = list(rack_segments)
            orig_spine_centerlines = list(spine_centerlines)
            orig_water_cluster_segments = list(water_cluster_segments)
            
            def to_tuple_seg(seg):
                if seg is None: return None
                p1 = (round(seg[0][0], 3), round(seg[0][1], 3))
                p2 = (round(seg[1][0], 3), round(seg[1][1], 3))
                return (p1, p2) if p1 < p2 else (p2, p1)

            # Helper to check if a point lies on a segment
            def pt_on_seg(p, seg):
                (x1, y1), (x2, y2) = seg
                x, y = p
                if abs(x1 - x2) < 0.1: # Vertical
                    return abs(x - x1) < 0.1 and min(y1, y2) - 0.1 <= y <= max(y1, y2) + 0.1
                else: # Horizontal
                    return abs(y - y1) < 0.1 and min(x1, x2) - 0.1 <= x <= max(x1, x2) + 0.1

            critical_segments = set()
            if pb_rect and ct_rect:
                import networkx as nx
                G_orig = nx.Graph()
                for seg in rack_segments:
                    p1 = (round(seg[0][0], 3), round(seg[0][1], 3))
                    p2 = (round(seg[1][0], 3), round(seg[1][1], 3))
                    G_orig.add_edge(p1, p2, original=seg)

                pb_nodes_orig = [(round(pt[0], 3), round(pt[1], 3)) for pt in pb_half] if pb_half else []
                ct_nodes_orig = [(round(pt[0], 3), round(pt[1], 3)) for pt in ct_half] if ct_half else []

                if pb_nodes_orig and ct_nodes_orig:
                    best_path = None
                    min_len = float('inf')
                    for u in pb_nodes_orig:
                        for v in ct_nodes_orig:
                            if u in G_orig and v in G_orig:
                                if nx.has_path(G_orig, u, v):
                                    path = nx.shortest_path(G_orig, source=u, target=v)
                                    if len(path) < min_len:
                                        min_len = len(path)
                                        best_path = path
                    if best_path:
                        for i in range(len(best_path) - 1):
                            edge_data = G_orig.get_edge_data(best_path[i], best_path[i+1])
                            if edge_data:
                                critical_segments.add(to_tuple_seg(edge_data["original"]))

            # 1) Trim Cooling Tower spine free ends.
            if ct_half is not None and ct_half in spine_centerlines:
                trimmed = cleanup_ct_free_ends(ct_half, rack_segments)
                if trimmed is None:
                    if to_tuple_seg(ct_half) not in critical_segments:
                        rack_segments = [s for s in rack_segments if s is not ct_half]
                        spine_centerlines = [s for s in spine_centerlines if s is not ct_half]
                        # Also prune any perpendicular connectors to this pruned spine
                        to_prune_conn = []
                        for seg in list(spine_centerlines):
                            if seg is not pb_half:
                                is_ct_vertical = abs(ct_half[0][0] - ct_half[1][0]) < 0.1
                                is_seg_vertical = abs(seg[0][0] - seg[1][0]) < 0.1
                                if is_ct_vertical != is_seg_vertical:
                                    if pt_on_seg(seg[0], ct_half) or pt_on_seg(seg[1], ct_half):
                                        # Protect main rack and bridge to pb_half
                                        is_main_rack = pt_on_seg((pb_cx, pb_cy), seg)
                                        is_bridge = (pb_half is not None) and (pt_on_seg(seg[0], pb_half) or pt_on_seg(seg[1], pb_half))
                                        if not is_main_rack and not is_bridge:
                                            if to_tuple_seg(seg) not in critical_segments:
                                                to_prune_conn.append(seg)
                        for seg in to_prune_conn:
                            if seg in rack_segments: rack_segments.remove(seg)
                            if seg in spine_centerlines: spine_centerlines.remove(seg)
                            if seg in water_cluster_segments: water_cluster_segments.remove(seg)
                elif trimmed != ct_half:
                    rack_segments = [trimmed if s is ct_half else s for s in rack_segments]
                    spine_centerlines = [trimmed if s is ct_half else s for s in spine_centerlines]

            # 1b) Trim Power Block spine free ends.
            if pb_half is not None and pb_half in spine_centerlines:
                trimmed = cleanup_ct_free_ends(pb_half, rack_segments)
                if trimmed is None:
                    if to_tuple_seg(pb_half) not in critical_segments:
                        rack_segments = [s for s in rack_segments if s is not pb_half]
                        spine_centerlines = [s for s in spine_centerlines if s is not pb_half]
                        # Also prune any perpendicular connectors to this pruned spine
                        to_prune_conn = []
                        for seg in list(spine_centerlines):
                            if seg is not ct_half:
                                is_pb_vertical = abs(pb_half[0][0] - pb_half[1][0]) < 0.1
                                is_seg_vertical = abs(seg[0][0] - seg[1][0]) < 0.1
                                if is_pb_vertical != is_seg_vertical:
                                    if pt_on_seg(seg[0], pb_half) or pt_on_seg(seg[1], pb_half):
                                        # Protect main rack and bridge to ct_half
                                        is_main_rack = pt_on_seg((pb_cx, pb_cy), seg)
                                        is_bridge = (ct_half is not None) and (pt_on_seg(seg[0], ct_half) or pt_on_seg(seg[1], ct_half))
                                        if not is_main_rack and not is_bridge:
                                            if to_tuple_seg(seg) not in critical_segments:
                                                to_prune_conn.append(seg)
                        for seg in to_prune_conn:
                            if seg in rack_segments: rack_segments.remove(seg)
                            if seg in spine_centerlines: spine_centerlines.remove(seg)
                            if seg in water_cluster_segments: water_cluster_segments.remove(seg)
                elif trimmed != pb_half:
                    rack_segments = [trimmed if s is pb_half else s for s in rack_segments]
                    spine_centerlines = [trimmed if s is pb_half else s for s in spine_centerlines]

            # 1c) Trim Water-cluster spine free ends. A water leaf often overshoots
            # ALONG a tank's rack-buffer edge to the far corner even though the rest
            # of the trunk already touches that buffer. We trim each water segment
            # back to its real JUNCTIONS, and keep the trim only if the network
            # STILL TOUCHES every water rack-buffer rectangle it touched before
            # (so RAW/Demi/WWT never get disconnected — touch anywhere on the
            # buffer counts, not just the original corner point).
            def _seg_touches_buffer(seg, rect, eps=1.0):
                (x0, y0), (x1, y1) = seg
                rx0, ry0, rw, rh = rect
                rx1, ry1 = rx0 + rw, ry0 + rh
                if abs(y0 - y1) < 0.1:                       # horizontal segment
                    y = y0; a, b = min(x0, x1), max(x0, x1)
                    for ey in (ry0, ry1):                    # lies on top/bottom edge
                        if abs(y - ey) < eps and max(a, rx0) <= min(b, rx1) + eps:
                            return True
                    for ex in (rx0, rx1):                    # crosses left/right edge
                        if a - eps <= ex <= b + eps and ry0 - eps <= y <= ry1 + eps:
                            return True
                elif abs(x0 - x1) < 0.1:                     # vertical segment
                    x = x0; a, b = min(y0, y1), max(y0, y1)
                    for ex in (rx0, rx1):
                        if abs(x - ex) < eps and max(a, ry0) <= min(b, ry1) + eps:
                            return True
                    for ey in (ry0, ry1):
                        if a - eps <= ey <= b + eps and rx0 - eps <= x <= rx1 + eps:
                            return True
                return False

            water_rects = {}
            for n in ("RAW Water Tank", "Demi Water Tank", "WT/WWT"):
                rect = rack_buffers.get(n, {}).get(active_cases.get(n))
                if rect:
                    water_rects[n] = rect

            if water_rects and water_cluster_segments:
                def _buffers_touched(segs):
                    return {n for n, rect in water_rects.items()
                            if any(_seg_touches_buffer(s, rect) for s in segs)}

                before_touch = _buffers_touched(rack_segments)
                for wseg in list(water_cluster_segments):
                    if not any(s is wseg for s in rack_segments):
                        continue
                    trimmed = cleanup_ct_free_ends(wseg, rack_segments)   # trim to junctions
                    if trimmed is None or trimmed == wseg:
                        continue
                    cand_rack = [trimmed if s is wseg else s for s in rack_segments]
                    if before_touch <= _buffers_touched(cand_rack):
                        rack_segments = cand_rack
                        water_cluster_segments = [trimmed if s is wseg else s for s in water_cluster_segments]

            # 2) Prune stub segments shorter than MIN_RACK_SEG_LEN.
            # We only prune segments that are shorter than MIN_RACK_SEG_LEN AND
            # have at least one endpoint of degree 1 (dead end) in the rack network.
            # We do this iteratively until no more stubs can be pruned.
            import networkx as nx
            while True:
                if _time_budget and (time.time() - _t_start) > _time_budget:
                    break
                G = nx.Graph()
                for seg in rack_segments:
                    p1 = (round(seg[0][0], 3), round(seg[0][1], 3))
                    p2 = (round(seg[1][0], 3), round(seg[1][1], 3))
                    G.add_edge(p1, p2, original=seg)
                
                to_prune = None
                for u, v, data in G.edges(data=True):
                    seg = data["original"]
                    length = math.hypot(seg[0][0] - seg[1][0], seg[0][1] - seg[1][1])
                    if length < MIN_RACK_SEG_LEN:
                        # Prune if either endpoint is a leaf (degree 1) in the graph
                        if G.degree(u) == 1 or G.degree(v) == 1:
                            if to_tuple_seg(seg) not in critical_segments:
                                to_prune = seg
                                break
                if to_prune is not None:
                    rack_segments.remove(to_prune)
                    if to_prune in spine_centerlines:
                        spine_centerlines.remove(to_prune)
                    if to_prune in water_cluster_segments:
                        water_cluster_segments.remove(to_prune)
                else:
                    break

            # Verify connection between Cooling Tower and Power Block
            if pb_rect and ct_rect:
                G_after = nx.Graph()
                for seg in rack_segments:
                    p1 = (round(seg[0][0], 3), round(seg[0][1], 3))
                    p2 = (round(seg[1][0], 3), round(seg[1][1], 3))
                    G_after.add_edge(p1, p2, original=seg)
                
                pb_nodes_after = [(round(pt[0], 3), round(pt[1], 3)) for pt in pb_half] if pb_half else []
                ct_nodes_after = [(round(pt[0], 3), round(pt[1], 3)) for pt in ct_half] if ct_half else []
                
                has_conn = False
                if pb_nodes_after and ct_nodes_after:
                    for u in pb_nodes_after:
                        for v in ct_nodes_after:
                            if u in G_after and v in G_after:
                                if nx.has_path(G_after, u, v):
                                    has_conn = True
                                    break
                        if has_conn:
                            break
                
                if not has_conn and critical_segments:
                    for seg in orig_rack_segments:
                        if to_tuple_seg(seg) in critical_segments:
                            if seg not in rack_segments:
                                rack_segments.append(seg)
                            if seg in orig_spine_centerlines and seg not in spine_centerlines:
                                spine_centerlines.append(seg)
                            if seg in orig_water_cluster_segments and seg not in water_cluster_segments:
                                water_cluster_segments.append(seg)

            # Track pruned segments
            for seg in orig_rack_segments:
                if seg not in rack_segments and seg not in pruned_rack_segments:
                    pruned_rack_segments.append(seg)

        # Clean tiny 1-grid jogs (A* snapping artefacts) from the rack network,
        # e.g. a y=101 run and y=102 run bridged by a 1 m vertical jog in the
        # PB↔CT spine connection — snap them collinear.
        rack_segments = _remove_tiny_jogs(rack_segments)

        # -----------------------------------------------------------------
        # Step 10.9 — Recenter (pre-roads)  [→ §3.8]
        # Recenter the placed layout (blocks + racks + ring road + gate) by
        # sliding the plot polygon onto the NON-ROAD content bbox center,
        # BEFORE access roads are generated. This is §3.8's recenter logic with
        # access-road geometry dropped from the bbox (none exists yet). Blocks,
        # racks, ring road and ring spur keep their coordinates — the plot frame
        # (and the gate, which belongs to the plot) moves around them. Access
        # roads are then placed around the already-centered layout and connect
        # to the recentered gate spur, so they never need recentering afterward.
        # -----------------------------------------------------------------
        PRE_RECENTER_ENABLED = True
        _pre_recenter_done = False
        recenter_delta = (0.0, 0.0)
        plot_polygon_before = list(plot.vertices) if plot is not None else None
        # Real CAD boundary BEFORE recenter (the inset's original_plot) — for
        # the dashboard's "before recenter" overlay, which shows the REAL plot.
        plot_polygon_original_before = (list(plot.original_plot.vertices)
                                        if plot is not None and getattr(plot, "original_plot", None) is not None
                                        else None)
        plot_bounds_before = ((plot.bbox[0], plot.bbox[1], plot.size[0], plot.size[1])
                              if plot is not None else (0.0, 0.0, sw, sl))
        gate_pt_before = gate_pt

        if PRE_RECENTER_ENABLED and plot is not None:
            def _pre_content_pts():
                for b in blocks:
                    yield (b["x"], b["y"])
                    yield (b["x"] + b["width"], b["y"] + b["height"])
                for poly in (ring_road, gate_road_out, ring_spur_out, boom_out):
                    if poly:
                        for p in poly:
                            yield (p[0], p[1])
                for segs in (rack_segments, water_cluster_segments):
                    if segs:
                        for s in segs:
                            yield (s[0][0], s[0][1])
                            yield (s[1][0], s[1][1])

            _cpts = list(_pre_content_pts())
            if _cpts:
                # Plot center = AREA CENTROID, not bbox center: with slanted
                # edges the polygon's mass sits away from the bbox middle, and
                # centering on the bbox systematically biases the layout toward
                # the cut-off side.
                _plot_cx, _plot_cy = plot.centroid
                _minx = min(p[0] for p in _cpts); _maxx = max(p[0] for p in _cpts)
                _miny = min(p[1] for p in _cpts); _maxy = max(p[1] for p in _cpts)
                _ccx, _ccy = (_minx + _maxx) / 2.0, (_miny + _maxy) / 2.0
                _fdx, _fdy = (_ccx - _plot_cx, _ccy - _plot_cy)

                _dx, _dy = 0.0, 0.0
                if abs(_fdx) > 0.01 or abs(_fdy) > 0.01:
                    # Containment clamp (same as §3.8): scale delta to the
                    # largest fraction that keeps every content point at least
                    # as deep inside the plot as it started (0.5 m slack for
                    # grid points on the boundary). PER-POINT requirement — a
                    # single point that already pokes past the boundary must
                    # not license every other point to sink that far too.
                    # The gate spur's final L to the gate is REBUILT after the
                    # move (§3.8 step 6) and its points sit on the boundary by
                    # definition — exclude them from the clamp.
                    _gate_tail = set()
                    if (gate_road_out and len(gate_road_out) >= 2 and gate_pt is not None
                            and abs(gate_road_out[-1][0] - gate_pt[0]) < 0.5
                            and abs(gate_road_out[-1][1] - gate_pt[1]) < 0.5):
                        _gate_tail = {(round(gate_road_out[-1][0], 3), round(gate_road_out[-1][1], 3)),
                                      (round(gate_road_out[-2][0], 3), round(gate_road_out[-2][1], 3))}
                    _clamp_pts = [q for q in _cpts
                                  if (round(q[0], 3), round(q[1], 3)) not in _gate_tail] or _cpts
                    _req = [min(plot.signed_dist_to_boundary(q[0], q[1]), 0.5) for q in _clamp_pts]

                    def _worst_margin(vx, vy, t):
                        return min(plot.signed_dist_to_boundary(q[0] - t * vx, q[1] - t * vy) - r
                                   for q, r in zip(_clamp_pts, _req))

                    def _max_t(vx, vy):
                        if abs(vx) < 1e-9 and abs(vy) < 1e-9:
                            return 0.0
                        if _worst_margin(vx, vy, 1.0) >= -1e-6:
                            return 1.0
                        _lo, _hi = 0.0, 1.0
                        for _ in range(20):
                            _mid = (_lo + _hi) / 2.0
                            if _worst_margin(vx, vy, _mid) >= -1e-6:
                                _lo = _mid
                            else:
                                _hi = _mid
                        return _lo

                    # Clamp each axis INDEPENDENTLY: a pinch in y (e.g. a block
                    # on the bottom edge) must not also cut the x slide, and
                    # vice versa. Then re-verify the combined vector once —
                    # slanted edges respond to diagonal moves, so the two
                    # axis-safe moves together may still need a final scale.
                    _cdx = _fdx * _max_t(_fdx, 0.0)
                    _cdy = _fdy * _max_t(0.0, _fdy)
                    _t_j = _max_t(_cdx, _cdy)
                    _dx, _dy = _cdx * _t_j, _cdy * _t_j
                    # Damping: apply only half of the (clamped) slide. The full
                    # clamped delta parks the pinned content (e.g. a CAD-anchored
                    # block near the boundary) exactly ON the temporary boundary;
                    # halving splits the remaining margin between both sides.
                    RECENTER_DAMPING = 0.5
                    _dx *= RECENTER_DAMPING
                    _dy *= RECENTER_DAMPING

                if abs(_dx) > 0.01 or abs(_dy) > 0.01:
                    recenter_delta = (_dx, _dy)
                    # Slide the plot polygon.
                    plot = plot.translate(_dx, _dy)
                    # Move the gate perpendicular to its edge only (keeps it on
                    # the moved boundary without sliding along the edge).
                    if gate_pt is not None:
                        _e = plot.edges[plot.nearest_edge(gate_pt[0], gate_pt[1])]
                        _ux, _uy = _e["dir"]
                        _along = _dx * _ux + _dy * _uy
                        gate_pt = (gate_pt[0] + _dx - _along * _ux,
                                   gate_pt[1] + _dy - _along * _uy)

                    def _same_pt(a, b):
                        return abs(a[0] - b[0]) < 0.5 and abs(a[1] - b[1]) < 0.5

                    # Rebuild the gate spur's final L so it reaches the moved gate.
                    if (gate_road_out and len(gate_road_out) >= 3 and gate_pt_before is not None
                            and _same_pt(gate_road_out[-1], gate_pt_before)):
                        oc = gate_road_out[-3]
                        l_old = gate_road_out[-2]
                        ng = gate_pt
                        if abs(l_old[1] - oc[1]) < 0.5:
                            l_new = (ng[0], oc[1])
                        else:
                            l_new = (oc[0], ng[1])
                        gate_road_out = list(gate_road_out[:-2]) + [l_new, ng]
                    elif (gate_road_out and gate_pt_before is not None
                          and _same_pt(gate_road_out[0], gate_pt_before)):
                        gate_road_out = [gate_pt] + list(gate_road_out[1:])

                    # Recompute the gate death zone between the fixed boom mid
                    # and the moved gate.
                    if gate_death_zone is not None and bb_mid is not None and gate_pt is not None:
                        _gx0, _gx1 = min(bb_mid[0], gate_pt[0]), max(bb_mid[0], gate_pt[0])
                        _gy0, _gy1 = min(bb_mid[1], gate_pt[1]), max(bb_mid[1], gate_pt[1])
                        if _gx1 - _gx0 < 1: _gx0 -= 1; _gx1 += 1
                        if _gy1 - _gy0 < 1: _gy0 -= 1; _gy1 += 1
                        gate_death_zone = (_gx0, _gy0, _gx1 - _gx0, _gy1 - _gy0)

                    _pre_recenter_done = True

        # -----------------------------------------------------------------
        # Step 11 — Clean opposite side road connection logic
        # -----------------------------------------------------------------
        def dist_to_road(p, road_segs):
            min_d = float('inf')
            for seg in road_segs:
                a, b = seg
                d = point_to_segment_distance(p, a, b)
                if d < min_d:
                    min_d = d
            return min_d

        CONNECT_BLOCKS = {"Cooling Tower", "Admin Building", "GIS", "WT/WWT", "Warehouse"}
        access_roads = []
        access_roads_blocks = []
        access_roads_parts = []
        
        road_segments = []
        if ring_road:
            for i in range(len(ring_road) - 1):
                road_segments.append((ring_road[i], ring_road[i+1]))
            road_segments.append((ring_road[-1], ring_road[0]))
        # Use gate_road_out and ring_spur_out if present, otherwise fallback to gate_spur and ring_spur
        live_gate_spur = gate_road_out if gate_road_out else gate_spur
        live_ring_spur = ring_spur_out if ring_spur_out else ring_spur
        if live_ring_spur:
            for i in range(len(live_ring_spur) - 1):
                road_segments.append((live_ring_spur[i], live_ring_spur[i+1]))
        gate_spur_segments = []
        if live_gate_spur:
            for i in range(len(live_gate_spur) - 1):
                gate_spur_segments.append((live_gate_spur[i], live_gate_spur[i+1]))

        # Forbidden Zone calculation based on distance < 100m between gate spur and ring road
        forbidden_zone_bbox = None
        if ring_road and bb_mid is not None and gate_pt is not None:
            rxs = [p[0] for p in ring_road]
            rys = [p[1] for p in ring_road]
            ring_y_max = max(rys)
            ring_y_min = min(rys)
            ring_x_max = max(rxs)
            ring_x_left = min(rxs)
            
            # Identify the start/end points of the boom barrier
            if boom_out:
                bb_pts = list(boom_out)
            else:
                if bb_edge_eff in ("N", "S"):
                    bb_pts = [(bb_mid[0] - 8, bb_mid[1]), (bb_mid[0] + 8, bb_mid[1])]
                else:
                    bb_pts = [(bb_mid[0], bb_mid[1] - 8), (bb_mid[0], bb_mid[1] + 8)]
            
            if gate_side == "N":
                ref_coord = ring_y_max
                # Use the boom barrier endpoint that is farthest to the ring road (max Y)
                bb_y = max(p[1] for p in bb_pts)
                spur_coord = min(bb_y, gate_pt[1])
                dist = spur_coord - ref_coord
                if dist > 0 and dist < 100.0:
                    # Choose farthest point to boom midpoint on the X axis among all points
                    all_pts = bb_pts + list(ring_road) + [gate_pt]
                    far_pt = max(all_pts, key=lambda p: abs(p[0] - bb_mid[0]))
                    x_far = far_pt[0]
                    x_min = min(bb_mid[0], x_far)
                    x_max = max(bb_mid[0], x_far)
                    y_min = ref_coord
                    y_max = spur_coord
                    forbidden_zone_bbox = (x_min, y_min, x_max - x_min, y_max - y_min)
            elif gate_side == "S":
                ref_coord = ring_y_min
                # Use the boom barrier endpoint that is farthest to the ring road (min Y)
                bb_y = min(p[1] for p in bb_pts)
                spur_coord = max(bb_y, gate_pt[1])
                dist = ref_coord - spur_coord
                if dist > 0 and dist < 100.0:
                    # Choose farthest point to boom midpoint on the X axis among all points
                    all_pts = bb_pts + list(ring_road) + [gate_pt]
                    far_pt = max(all_pts, key=lambda p: abs(p[0] - bb_mid[0]))
                    x_far = far_pt[0]
                    x_min = min(bb_mid[0], x_far)
                    x_max = max(bb_mid[0], x_far)
                    y_min = spur_coord
                    y_max = ref_coord
                    forbidden_zone_bbox = (x_min, y_min, x_max - x_min, y_max - y_min)
            elif gate_side == "E":
                ref_coord = ring_x_max
                # Use the boom barrier endpoint that is farthest to the ring road (max X)
                bb_x = max(p[0] for p in bb_pts)
                spur_coord = min(bb_x, gate_pt[0])
                dist = spur_coord - ref_coord
                if dist > 0 and dist < 100.0:
                    # Choose farthest point to boom midpoint on the Y axis among all points
                    all_pts = bb_pts + list(ring_road) + [gate_pt]
                    far_pt = max(all_pts, key=lambda p: abs(p[1] - bb_mid[1]))
                    y_far = far_pt[1]
                    y_min = min(bb_mid[1], y_far)
                    y_max = max(bb_mid[1], y_far)
                    x_min = ref_coord
                    x_max = spur_coord
                    forbidden_zone_bbox = (x_min, y_min, x_max - x_min, y_max - y_min)
            elif gate_side == "W":
                ref_coord = ring_x_left
                # Use the boom barrier endpoint that is farthest to the ring road (min X)
                bb_x = min(p[0] for p in bb_pts)
                spur_coord = max(bb_x, gate_pt[0])
                dist = ref_coord - spur_coord
                if dist > 0 and dist < 100.0:
                    # Choose farthest point to boom midpoint on the Y axis among all points
                    all_pts = bb_pts + list(ring_road) + [gate_pt]
                    far_pt = max(all_pts, key=lambda p: abs(p[1] - bb_mid[1]))
                    y_far = far_pt[1]
                    y_min = min(bb_mid[1], y_far)
                    y_max = max(bb_mid[1], y_far)
                    x_min = spur_coord
                    x_max = ref_coord
                    forbidden_zone_bbox = (x_min, y_min, x_max - x_min, y_max - y_min)

        # Dynamic exclusion of blocks overlapping the forbidden zone
        final_connect_blocks = set(CONNECT_BLOCKS)
        if forbidden_zone_bbox is not None:
            f_x, f_y, f_w, f_h = forbidden_zone_bbox
            for b in blocks:
                if b["name"] in final_connect_blocks:
                    bx, by, bw, bh = b["x"], b["y"], b["width"], b["height"]
                    # Match tolerance (5.0m) of is_block_in_forbidden_zone to catch blocks right at the edge
                    overlap_x = not (bx + bw + 5.0 <= f_x or f_x + f_w + 5.0 <= bx)
                    overlap_y = not (by + bh + 5.0 <= f_y or f_y + f_h + 5.0 <= by)
                    if overlap_x and overlap_y:
                        final_connect_blocks.remove(b["name"])
        CONNECT_BLOCKS = final_connect_blocks
                
        import numpy as np
        # Hard clearance: block the footprint cells plus a 2 m skirt so no
        # access road can ever be routed on or right against a block footprint.
        # The road buffers below stay a SOFT, graded guide (§3.7).
        grid_roads = Grid(sw, sl, cell_size=CELL_SIZE)
        for b in blocks:
            grid_roads.mark_building(b, inflate_m=2.0)

        # if plot is not None:
        #     inside_mask = plot.cell_inside_mask(grid_roads.ncols, grid_roads.nrows, grid_roads.cell_size)
        #     for i in range(grid_roads.ncols):
        #         for j in range(grid_roads.nrows):
        #             if not inside_mask[i][j]:
        #                 grid_roads.blocked[i, j] = True

        # Block grid cells within the forbidden zone
        if forbidden_zone_bbox is not None:
            f_x, f_y, f_w, f_h = forbidden_zone_bbox
            i0, j0 = grid_roads.world_to_cell(f_x, f_y)
            i1, j1 = grid_roads.world_to_cell(f_x + f_w, f_y + f_h)
            for i in range(i0, i1 + 1):
                for j in range(j0, j1 + 1):
                    if grid_roads.in_bounds(i, j):
                        grid_roads.blocked[i, j] = True

        unblock_segments_on_grid(grid_roads, road_segments)
        unblock_segments_on_grid(grid_roads, gate_spur_segments)
        
        # Graded buffer penalty: 500 right at the footprint, falling linearly
        # to 0 at the road-buffer edge. The buffer is a GUIDE, not a wall —
        # A* is pushed away from footprints and prefers running along the
        # buffer edge line (where P_buf and the Part 2 rectangle R sit)
        # instead of hugging the block at 1-2 cells like a flat penalty allows.
        buffer_penalty = np.zeros((grid_roads.ncols, grid_roads.nrows), dtype=float)
        for b in blocks:
            b_offset = 16.0 if b["name"] in RACK_BLOCKS else 8.0
            x0 = b["x"] - b_offset
            y0 = b["y"] - b_offset
            x1 = b["x"] + b["width"] + b_offset
            y1 = b["y"] + b["height"] + b_offset

            i0, j0 = grid_roads.world_to_cell(x0, y0)
            i1, j1 = grid_roads.world_to_cell(x1, y1)
            for i in range(i0, i1 + 1):
                for j in range(j0, j1 + 1):
                    if grid_roads.in_bounds(i, j) and not grid_roads.blocked[i, j]:
                        cx, cy = grid_roads.cell_to_world(i, j)
                        ddx = max(b["x"] - cx, 0.0, cx - (b["x"] + b["width"]))
                        ddy = max(b["y"] - cy, 0.0, cy - (b["y"] + b["height"]))
                        d_foot = math.hypot(ddx, ddy)
                        pen = 500.0 * max(0.0, 1.0 - d_foot / b_offset)
                        if pen > buffer_penalty[i, j]:
                            buffer_penalty[i, j] = pen

        # Rack clearance: roads may CROSS a rack (perpendicular), but must not
        # run PARALLEL alongside one within RACK_ROAD_CLEAR (8 m) of its
        # centerline. Direction-aware A* penalties: horizontal moves are walled
        # near HORIZONTAL racks, vertical moves near VERTICAL racks — so
        # crossing a rack band perpendicular costs nothing, while running
        # along it is a flat wall (A* leaves the band and runs right at the
        # 8 m line instead of alongside the rack).
        RACK_ROAD_CLEAR = 8.0

        def _seg_pt_dist(px, py, ax, ay, bx, by):
            dx, dy = bx - ax, by - ay
            l2 = dx * dx + dy * dy
            if l2 < 1e-9:
                return math.hypot(px - ax, py - ay)
            t = ((px - ax) * dx + (py - ay) * dy) / l2
            t = max(0.0, min(1.0, t))
            return math.hypot(px - (ax + t * dx), py - (ay + t * dy))

        rack_penalty_h = np.zeros((grid_roads.ncols, grid_roads.nrows), dtype=float)
        rack_penalty_v = np.zeros((grid_roads.ncols, grid_roads.nrows), dtype=float)
        for seg in rack_segments:
            (rax, ray), (rbx, rby) = seg
            rack_horizontal = abs(rby - ray) <= abs(rbx - rax)
            target = rack_penalty_h if rack_horizontal else rack_penalty_v
            rx0 = min(rax, rbx) - RACK_ROAD_CLEAR; rx1 = max(rax, rbx) + RACK_ROAD_CLEAR
            ry0 = min(ray, rby) - RACK_ROAD_CLEAR; ry1 = max(ray, rby) + RACK_ROAD_CLEAR
            i0, j0 = grid_roads.world_to_cell(rx0, ry0)
            i1, j1 = grid_roads.world_to_cell(rx1, ry1)
            for i in range(i0, i1 + 1):
                for j in range(j0, j1 + 1):
                    if grid_roads.in_bounds(i, j) and not grid_roads.blocked[i, j]:
                        cx, cy = grid_roads.cell_to_world(i, j)
                        d = _seg_pt_dist(cx, cy, rax, ray, rbx, rby)
                        if d < RACK_ROAD_CLEAR - 0.1:
                            pen = 3000.0 + (RACK_ROAD_CLEAR - d)
                            if pen > target[i, j]:
                                target[i, j] = pen

        for seg in road_segments + gate_spur_segments:
            p1, p2 = seg
            x1, y1 = p1
            x2, y2 = p2
            dist = math.hypot(x2 - x1, y2 - y1)
            if dist < 0.1:
                i, j = grid_roads.world_to_cell(x1, y1)
                if grid_roads.in_bounds(i, j):
                    buffer_penalty[i, j] = 0.0
                    rack_penalty_h[i, j] = 0.0
                    rack_penalty_v[i, j] = 0.0
                continue
            steps = int(math.ceil(dist / (grid_roads.cell_size / 2)))
            for s in range(steps + 1):
                t = s / steps
                cx = x1 + t * (x2 - x1)
                cy = y1 + t * (y2 - y1)
                i, j = grid_roads.world_to_cell(cx, cy)
                if grid_roads.in_bounds(i, j):
                    buffer_penalty[i, j] = 0.0
                    rack_penalty_h[i, j] = 0.0
                    rack_penalty_v[i, j] = 0.0

        road_segments_p1 = list(road_segments)
        road_segments_all = list(road_segments)

        road_cells_p1 = set()
        for seg in road_segments_p1:
            p1, p2 = seg
            x1, y1 = p1
            x2, y2 = p2
            dist = math.hypot(x2 - x1, y2 - y1)
            if dist < 0.1:
                i, j = grid_roads.world_to_cell(x1, y1)
                if grid_roads.in_bounds(i, j):
                    road_cells_p1.add((i, j))
                continue
            steps = int(math.ceil(dist / (grid_roads.cell_size / 2)))
            for s in range(steps + 1):
                t = s / steps
                cx = x1 + t * (x2 - x1)
                cy = y1 + t * (y2 - y1)
                i, j = grid_roads.world_to_cell(cx, cy)
                if grid_roads.in_bounds(i, j):
                    road_cells_p1.add((i, j))

        road_cells_all = set(road_cells_p1)

        def _path_runs_along_rack(path):
            return any(segment_near_rack(path[k], path[k + 1])
                       for k in range(len(path) - 1))

        def route_from_point(P_start, segments, cells):
            P_goal = find_closest_point_on_road(P_start, segments)
            l_path1 = [P_start, (P_goal[0], P_start[1]), P_goal]
            l_path2 = [P_start, (P_start[0], P_goal[1]), P_goal]

            if is_path_clear_of_buffers(grid_roads, l_path1, buffer_penalty) and not _path_runs_along_rack(l_path1):
                return l_path1
            if is_path_clear_of_buffers(grid_roads, l_path2, buffer_penalty) and not _path_runs_along_rack(l_path2):
                return l_path2

            c_start = grid_roads.world_to_cell(*P_start)
            if not grid_roads.in_bounds(*c_start):
                return l_path1

            was_blocked = grid_roads.blocked[c_start]
            grid_roads.blocked[c_start] = False

            def astar_cell_cost(cell, next_cell):
                # Direction-aware rack wall: horizontal moves are penalised
                # near horizontal racks, vertical moves near vertical racks —
                # crossing a rack perpendicular stays free.
                pen = buffer_penalty[next_cell[0], next_cell[1]]
                if next_cell[0] != cell[0]:
                    pen += rack_penalty_h[next_cell[0], next_cell[1]]
                elif next_cell[1] != cell[1]:
                    pen += rack_penalty_v[next_cell[0], next_cell[1]]
                return pen

            astar_path = astar(grid_roads, c_start, cells, width_cells=0, allow_diagonal=False, turn_penalty=50.0, cell_cost_fn=astar_cell_cost)
            grid_roads.blocked[c_start] = was_blocked
            
            if astar_path:
                return [grid_roads.cell_to_world(*c) for c in astar_path]
            # Last resort (A* failed): prefer an L-path that at least does not
            # cross a block footprint (+2 m skirt)
            if not is_path_clear(grid_roads, l_path1) and is_path_clear(grid_roads, l_path2):
                return l_path2
            return l_path1

        def add_path_to_road_network(path, segments, cells):
            for idx in range(len(path) - 1):
                p1, p2 = path[idx], path[idx+1]
                segments.append((p1, p2))
                x1, y1 = p1
                x2, y2 = p2
                dist = math.hypot(x2 - x1, y2 - y1)
                if dist < 0.1:
                    cell = grid_roads.world_to_cell(x1, y1)
                    if grid_roads.in_bounds(*cell):
                        cells.add(cell)
                        buffer_penalty[cell[0], cell[1]] = 0.0
                        rack_penalty_h[cell[0], cell[1]] = 0.0
                        rack_penalty_v[cell[0], cell[1]] = 0.0
                    continue
                steps = int(math.ceil(dist / (grid_roads.cell_size / 2)))
                for s in range(steps + 1):
                    t = s / steps
                    cx = x1 + t * (x2 - x1)
                    cy = y1 + t * (y2 - y1)
                    cell = grid_roads.world_to_cell(cx, cy)
                    if grid_roads.in_bounds(*cell):
                        cells.add(cell)
                        buffer_penalty[cell[0], cell[1]] = 0.0
                        rack_penalty_h[cell[0], cell[1]] = 0.0
                        rack_penalty_v[cell[0], cell[1]] = 0.0

        def is_block_in_forbidden_zone(b, f_zone):
            if f_zone is None:
                return False
            f_x, f_y, f_w, f_h = f_zone
            bx, by, bw, bh = b["x"], b["y"], b["width"], b["height"]
            # Tolerance to catch blocks right at the edge
            overlap_x = not (bx + bw + 5.0 <= f_x or f_x + f_w + 5.0 <= bx)
            overlap_y = not (by + bh + 5.0 <= f_y or f_y + f_h + 5.0 <= by)
            return overlap_x and overlap_y

        def align_terminal_to_network(p, road_segments):
            if not p or not road_segments:
                return p
            px, py = p
            min_d = float('inf')
            closest_pt = p
            for s0, s1 in road_segments:
                x1, y1 = s0
                x2, y2 = s1
                dx, dy = x2 - x1, y2 - y1
                l2 = dx*dx + dy*dy
                if l2 < 1e-9:
                    d = math.hypot(px - x1, py - y1)
                    if d < min_d:
                        min_d = d
                        closest_pt = (x1, y1)
                    continue
                t = ((px - x1) * dx + (py - y1) * dy) / l2
                t = max(0.0, min(1.0, t))
                c_x = x1 + t * dx
                c_y = y1 + t * dy
                d = math.hypot(px - c_x, py - c_y)
                if d < min_d:
                    min_d = d
                    closest_pt = (c_x, c_y)
            return closest_pt

        def straighten_arrival(path, target_segments, tol):
            # §3.7.B step 7 — make the arrival run straight and turn only once,
            # at the network. Mutates `path` in place (access_roads holds it).
            # A slide is committed ONLY if the new tail keeps clear of every
            # block footprint (>= 4 m); otherwise the orthogonal stub is kept,
            # because footprint clearance outranks the single-turn cosmetic.
            foot_clear = 4.0

            def _leg_clears(a, b):
                sx0, sx1 = min(a[0], b[0]), max(a[0], b[0])
                sy0, sy1 = min(a[1], b[1]), max(a[1], b[1])
                for b2 in blocks:
                    bx0, by0 = b2["x"] - foot_clear, b2["y"] - foot_clear
                    bx1 = b2["x"] + b2["width"] + foot_clear
                    by1 = b2["y"] + b2["height"] + foot_clear
                    if sx1 >= bx0 and sx0 <= bx1 and sy1 >= by0 and sy0 <= by1:
                        return False
                # A slide must also not push the leg within 8 m of a rack CL.
                if segment_near_rack(a, b):
                    return False
                return True

            def _tail_clears(cand):
                # Only the last two segments change in a slide — check those.
                lo = max(0, len(cand) - 3)
                return all(_leg_clears(cand[i], cand[i + 1]) for i in range(lo, len(cand) - 1))

            # (a) Stub pattern: a long leg parallel to the target road line a
            #     few cells away, ending in a tiny stub onto the connection
            #     point. Slide the offset leg onto the connection point's line.
            #     ITERATE: an A* tail can be a staircase of small steps — each
            #     slide exposes the next stub, so repeat until stable.
            for _a_iter in range(8):
                if len(path) < 4:
                    break
                pD, pC, pB = path[-1], path[-2], path[-3]
                stub = math.hypot(pD[0] - pC[0], pD[1] - pC[1])
                if not (0.1 < stub <= tol):
                    break
                stub_horizontal = abs(pD[1] - pC[1]) <= abs(pD[0] - pC[0])
                cand = None
                if stub_horizontal and abs(pC[0] - pB[0]) < 0.1:
                    # vertical leg offset from x=pD.x — slide onto pD's line
                    cand = path[:-3] + [(pD[0], pB[1]), pD]
                elif not stub_horizontal and abs(pC[1] - pB[1]) < 0.1:
                    # horizontal leg offset from y=pD.y — slide onto pD's line
                    cand = path[:-3] + [(pB[0], pD[1]), pD]
                if cand is None or not _tail_clears(cand):
                    break
                path[:] = cand
            # (b) Offset-terminal pattern: the final leg runs parallel to a
            #     network road line (ring road edge, ring spur leg, an earlier
            #     access road, ...) a cell or two beside it, its terminal
            #     ending next to that line (A* cell rounding, no stub drawn).
            #     Projecting to the single nearest network point misses this
            #     (near a corner the nearest segment is the perpendicular one),
            #     so search for the parallel target line explicitly and slide
            #     the whole leg sideways onto it.
            if len(path) >= 3 and target_segments:
                cell_tol = 2.0 * grid_roads.cell_size
                pC, pB = path[-1], path[-2]
                if abs(pC[0] - pB[0]) < 0.1:  # vertical leg
                    best = None
                    for s0, s1 in target_segments:
                        if abs(s0[0] - s1[0]) >= 0.1:
                            continue  # target not vertical
                        d_side = abs(s0[0] - pC[0])
                        if not (0.1 < d_side <= cell_tol):
                            continue
                        smin, smax = min(s0[1], s1[1]), max(s0[1], s1[1])
                        if smin - cell_tol <= pC[1] <= smax + cell_tol:
                            if best is None or d_side < best[0]:
                                best = (d_side, s0[0], smin, smax)
                    if best:
                        _, tx, smin, smax = best
                        ty = min(max(pC[1], smin), smax)  # land on the segment
                        cand = path[:-2] + [(snap(tx), pB[1]), (snap(tx), snap(ty))]
                        if _tail_clears(cand):
                            path[:] = cand
                elif abs(pC[1] - pB[1]) < 0.1:  # horizontal leg
                    best = None
                    for s0, s1 in target_segments:
                        if abs(s0[1] - s1[1]) >= 0.1:
                            continue  # target not horizontal
                        d_side = abs(s0[1] - pC[1])
                        if not (0.1 < d_side <= cell_tol):
                            continue
                        smin, smax = min(s0[0], s1[0]), max(s0[0], s1[0])
                        if smin - cell_tol <= pC[0] <= smax + cell_tol:
                            if best is None or d_side < best[0]:
                                best = (d_side, s0[1], smin, smax)
                    if best:
                        _, ty, smin, smax = best
                        tx = min(max(pC[0], smin), smax)  # land on the segment
                        cand = path[:-2] + [(pB[0], snap(ty)), (snap(tx), snap(ty))]
                        if _tail_clears(cand):
                            path[:] = cand
            # Dedup in case a slide collapsed two points together
            if path:
                dedup = [path[0]]
                for p in path[1:]:
                    if math.hypot(p[0] - dedup[-1][0], p[1] - dedup[-1][1]) > 0.1:
                        dedup.append(p)
                if len(dedup) >= 2:
                    path[:] = dedup

        def _path_cleanup(path):
            # dedup + collinear simplify, in place; endpoints preserved
            if len(path) < 2:
                return
            dd = [path[0]]
            for q in path[1:]:
                if math.hypot(q[0] - dd[-1][0], q[1] - dd[-1][1]) > 0.1:
                    dd.append(q)
            out = [dd[0]]
            for j in range(1, len(dd) - 1):
                ux, uy = dd[j][0] - out[-1][0], dd[j][1] - out[-1][1]
                vx, vy = dd[j + 1][0] - dd[j][0], dd[j + 1][1] - dd[j][1]
                if abs(ux * vy - uy * vx) > 1e-6:
                    out.append(dd[j])
            if len(dd) >= 2:
                out.append(dd[-1])
            if len(out) >= 2:
                path[:] = out

        def orthogonalize_path(path):
            # §3.7 — roads must be ORTHOGONAL. Split any diagonal segment into
            # an L, preferring the corner that continues the previous
            # segment's axis and keeps clear of footprints/racks.
            i = 0
            while i < len(path) - 1:
                a, b = path[i], path[i + 1]
                if abs(b[0] - a[0]) > 0.1 and abs(b[1] - a[1]) > 0.1:
                    c_h = (b[0], a[1])  # horizontal leg first
                    c_v = (a[0], b[1])  # vertical leg first
                    if i > 0 and abs(a[1] - path[i - 1][1]) < 0.1:
                        cands = [c_h, c_v]  # previous leg horizontal
                    elif i > 0:
                        cands = [c_v, c_h]
                    else:
                        cands = [c_h, c_v]
                    chosen = None
                    for c in cands:
                        if (not segment_hits_footprint(a, c) and not segment_hits_footprint(c, b)
                                and not segment_near_rack(a, c) and not segment_near_rack(c, b)):
                            chosen = c
                            break
                    path.insert(i + 1, chosen if chosen is not None else cands[0])
                    i += 2
                else:
                    i += 1
            _path_cleanup(path)

        def collapse_jogs(path, tol=4.0):
            # §3.7 — remove small zigzags (prefer plain L shapes): a short
            # perpendicular step (<= tol) next to a long leg slides the
            # neighbouring leg sideways onto the straight line. Path endpoints
            # (the loop junction and the network connection) never move.
            def _clear(a, b):
                return not segment_hits_footprint(a, b) and not segment_near_rack(a, b)

            changed = True
            while changed and len(path) >= 3:
                changed = False
                # tiny FIRST step: [A,B,C,...] with |AB| <= tol and AB ⊥ BC —
                # slide the BC leg onto A's axis (B removed, C projected).
                a, b, c = path[0], path[1], path[2]
                l1 = math.hypot(b[0] - a[0], b[1] - a[1])
                s1_vert = abs(b[0] - a[0]) < 0.1
                s2_vert = abs(c[0] - b[0]) < 0.1
                if l1 <= tol and s1_vert != s2_vert and len(path) >= 4:
                    # (len >= 4: c must not be the network endpoint)
                    c_new = (c[0], a[1]) if s1_vert else (a[0], c[1])
                    nxt = path[3]
                    ok = _clear(a, c_new) and _clear(c_new, nxt)
                    if ok:
                        path[1:3] = [c_new]
                        _path_cleanup(path)
                        changed = True
                        continue
                # tiny MIDDLE step: legs u — j (<= tol, ⊥) — u (same axis,
                # same sense): slide the shorter u-leg onto the other's line.
                for i in range(0, len(path) - 3):
                    p0, p1, p2, p3 = path[i], path[i + 1], path[i + 2], path[i + 3]
                    u1x, u1y = p1[0] - p0[0], p1[1] - p0[1]
                    jx, jy = p2[0] - p1[0], p2[1] - p1[1]
                    u2x, u2y = p3[0] - p2[0], p3[1] - p2[1]
                    jl = math.hypot(jx, jy)
                    u1_vert = abs(u1x) < 0.1 and abs(u1y) > 0.1
                    u2_vert = abs(u2x) < 0.1 and abs(u2y) > 0.1
                    u1_horz = abs(u1y) < 0.1 and abs(u1x) > 0.1
                    u2_horz = abs(u2y) < 0.1 and abs(u2x) > 0.1
                    same_axis = (u1_vert and u2_vert) or (u1_horz and u2_horz)
                    same_sense = (u1x * u2x + u1y * u2y) > 0
                    if not (0.1 < jl <= tol and same_axis and same_sense):
                        continue
                    l_u1 = math.hypot(u1x, u1y)
                    l_u2 = math.hypot(u2x, u2y)
                    # slide the shorter leg; never move path[0] / path[-1]
                    if l_u1 <= l_u2 and i > 0:
                        # move p0,p1 onto the p2-p3 line
                        if u1_vert:
                            n0, n1 = (p2[0], p0[1]), (p2[0], p1[1])
                        else:
                            n0, n1 = (p0[0], p2[1]), (p1[0], p2[1])
                        prev = path[i - 1]
                        if _clear(prev, n0) and _clear(n0, n1) and _clear(n1, p3):
                            path[i] = n0
                            path[i + 1] = n1
                            path[i + 2:i + 3] = []
                            _path_cleanup(path)
                            changed = True
                            break
                    elif l_u2 < l_u1 and i + 3 <= len(path) - 2:
                        # move p2,p3 onto the p0-p1 line
                        if u2_vert:
                            n2, n3 = (p1[0], p2[1]), (p1[0], p3[1])
                        else:
                            n2, n3 = (p2[0], p1[1]), (p3[0], p1[1])
                        nxt = path[i + 4]
                        if _clear(p1, n2) and _clear(n2, n3) and _clear(n3, nxt):
                            path[i + 2] = n2
                            path[i + 3] = n3
                            _path_cleanup(path)
                            changed = True
                            break

        def clip_point_to_plot(p, plot):
            return p

        def find_segment_intersection(s1, s2):
            (x1, y1), (x2, y2) = s1
            (x3, y3), (x4, y4) = s2
            TOL = 0.5
            h1 = abs(y1 - y2) < TOL
            h2 = abs(y3 - y4) < TOL
            if h1 and h2:
                if abs(y1 - y3) > TOL:
                    return None
                min_x = max(min(x1, x2), min(x3, x4))
                max_x = min(max(x1, x2), max(x3, x4))
                if min_x <= max_x + TOL:
                    return (min_x, y1)
                return None
            if not h1 and not h2:
                if abs(x1 - x3) > TOL:
                    return None
                min_y = max(min(y1, y2), min(y3, y4))
                max_y = min(max(y1, y2), max(y3, y4))
                if min_y <= max_y + TOL:
                    return (x1, min_y)
                return None
            if h1 and not h2:
                hy = y1
                min_hx, max_hx = min(x1, x2), max(x1, x2)
                vx = x3
                min_vy, max_vy = min(y3, y4), max(y3, y4)
                if min_hx - TOL <= vx <= max_hx + TOL and min_vy - TOL <= hy <= max_vy + TOL:
                    return (vx, hy)
                return None
            if not h1 and h2:
                vx = x1
                min_vy, max_vy = min(y1, y2), max(y1, y2)
                hy = y3
                min_hx, max_hx = min(x3, x4), max(x3, x4)
                if min_hx - TOL <= vx <= max_hx + TOL and min_vy - TOL <= hy <= max_vy + TOL:
                    return (vx, hy)
                return None
            return None

        def check_overlap(path1, path2, threshold=12.0, epsilon=5.0):
            if not path1 or not path2:
                return False
            def dist_to_segment(p, s0, s1):
                px, py = p
                x1, y1 = s0
                x2, y2 = s1
                dx = x2 - x1
                dy = y2 - y1
                if dx == 0 and dy == 0:
                    return math.hypot(px - x1, py - y1)
                t = ((px - x1) * dx + (py - y1) * dy) / (dx*dx + dy*dy)
                t = max(0.0, min(1.0, t))
                return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))
            def dist_to_path(p, path):
                min_d = float('inf')
                for i in range(len(path) - 1):
                    d = dist_to_segment(p, path[i], path[i+1])
                    if d < min_d:
                        min_d = d
                return min_d
            overlap_len = 0.0
            curr_dist_from_start = 0.0
            for idx in range(len(path2) - 1):
                p_start = path2[idx]
                p_end = path2[idx+1]
                seg_len = math.hypot(p_end[0] - p_start[0], p_end[1] - p_start[1])
                if seg_len < 0.1:
                    continue
                steps = int(math.ceil(seg_len / 1.0))
                for s in range(steps):
                    t = s / steps
                    curr_p = (p_start[0] + t * (p_end[0] - p_start[0]), p_start[1] + t * (p_end[1] - p_start[1]))
                    dist_start = curr_dist_from_start + t * seg_len
                    if dist_start > 10.0:
                        if dist_to_path(curr_p, path1) < threshold:
                            overlap_len += seg_len / steps
                curr_dist_from_start += seg_len
            return overlap_len > epsilon

        FOOT_CLEAR = 4.0  # min distance access roads keep from any footprint

        def segment_hits_footprint(p1, p2, clear=FOOT_CLEAR):
            # Axis-aligned segment vs footprint AABB (+clearance). Exact for
            # orthogonal segments, conservative for the rare diagonal one.
            sx0, sx1 = min(p1[0], p2[0]), max(p1[0], p2[0])
            sy0, sy1 = min(p1[1], p2[1]), max(p1[1], p2[1])
            for b2 in blocks:
                bx0 = b2["x"] - clear
                by0 = b2["y"] - clear
                bx1 = b2["x"] + b2["width"] + clear
                by1 = b2["y"] + b2["height"] + clear
                if sx1 >= bx0 and sx0 <= bx1 and sy1 >= by0 and sy0 <= by1:
                    return True
            return False

        def segment_near_rack(p1, p2, clear=RACK_ROAD_CLEAR):
            # True if the axis-aligned road segment p1-p2 runs PARALLEL to a
            # rack centerline within `clear` (8 m) with a real overlap. Roads
            # may CROSS racks (perpendicular) — only running alongside is
            # forbidden.
            road_horizontal = abs(p2[1] - p1[1]) <= abs(p2[0] - p1[0])
            for (rax, ray), (rbx, rby) in rack_segments:
                rack_horizontal = abs(rby - ray) <= abs(rbx - rax)
                if rack_horizontal != road_horizontal:
                    continue  # perpendicular → crossing allowed
                if road_horizontal:
                    if abs(ray - p1[1]) >= clear - 0.1:
                        continue
                    lo = max(min(p1[0], p2[0]), min(rax, rbx))
                    hi = min(max(p1[0], p2[0]), max(rax, rbx))
                else:
                    if abs(rax - p1[0]) >= clear - 0.1:
                        continue
                    lo = max(min(p1[1], p2[1]), min(ray, rby))
                    hi = min(max(p1[1], p2[1]), max(ray, rby))
                if hi - lo > 2.0:  # parallel side-by-side run longer than 2 m
                    return True
            return False

        def build_candidate_path(seq, P_buf, road_segments_all, path1_conn_pt):
            path_pts = [P_buf]
            clipped_P_buf = clip_point_to_plot(P_buf, plot)
            curr_pt = clipped_P_buf
            for target_corner in seq:
                clipped_corner = clip_point_to_plot(target_corner, plot)
                # Never trace across a block footprint, or within 8 m of a rack
                # centerline (can happen when a neighbouring block/rack sits on
                # this block's R rectangle, or a corner was clipped to the plot
                # boundary) — reject the whole candidate; fallback_connection
                # will route around via A* (which is rack-aware via penalties).
                if segment_hits_footprint(curr_pt, clipped_corner) or segment_near_rack(curr_pt, clipped_corner):
                    return None
                segment = (curr_pt, clipped_corner)
                intersections = []
                for road_seg in road_segments_all:
                    pt_int = find_segment_intersection(segment, road_seg)
                    if pt_int:
                        if path1_conn_pt is None or math.hypot(pt_int[0] - path1_conn_pt[0], pt_int[1] - path1_conn_pt[1]) >= 15.0:
                            d = math.hypot(pt_int[0] - curr_pt[0], pt_int[1] - curr_pt[1])
                            intersections.append((d, pt_int))
                if intersections:
                    intersections.sort(key=lambda x: x[0])
                    chosen_int = intersections[0][1]
                    return path_pts + [chosen_int]
                path_pts.append(clipped_corner)
                curr_pt = clipped_corner
            return None

        def fallback_connection(seq, P_buf, road_segments_all, road_cells_all, path1_conn_pt):
            best_path = None
            best_len = float('inf')
            clipped_P_buf = clip_point_to_plot(P_buf, plot)
            for idx, pt in enumerate([clipped_P_buf] + [clip_point_to_plot(c, plot) for c in seq]):
                path_along_R = [clipped_P_buf] + [clip_point_to_plot(c, plot) for c in seq[:idx]]
                if pt not in path_along_R:
                    path_along_R.append(pt)
                # The walk along R up to this corner must not cross a footprint
                # or run within 8 m of a rack centerline.
                if any(segment_hits_footprint(path_along_R[k], path_along_R[k + 1])
                       or segment_near_rack(path_along_R[k], path_along_R[k + 1])
                       for k in range(len(path_along_R) - 1)):
                    continue
                a_star_path = route_from_point(pt, road_segments_all, road_cells_all)
                if a_star_path and len(a_star_path) > 1:
                    conn_pt = a_star_path[-1]
                    if path1_conn_pt is None or math.hypot(conn_pt[0] - path1_conn_pt[0], conn_pt[1] - path1_conn_pt[1]) >= 15.0:
                        full_path = path_along_R + a_star_path[1:]
                        path_len = sum(math.hypot(full_path[i+1][0] - full_path[i][0], full_path[i+1][1] - full_path[i][1]) for i in range(len(full_path)-1))
                        if path_len < best_len:
                            best_len = path_len
                            best_path = full_path
            return best_path
            
        for b in blocks:
            b_name = b["name"]
            if b_name not in CONNECT_BLOCKS:
                continue
                
            bx, by, bw, bh = b["x"], b["y"], b["width"], b["height"]
            
            sides = {
                "N": ((bx + bw/2, by + bh), (0, 1)),
                "S": ((bx + bw/2, by), (0, -1)),
                "E": ((bx + bw, by + bh/2), (1, 0)),
                "W": ((bx, by + bh/2), (-1, 0))
            }
            
            # Improved Side Detection:
            # 1. Determine which sides have their buffer midpoint (P_buf) safely inside the plot
            valid_sides = {}
            for side_name, (midpt, sdir) in sides.items():
                B_offset_cand = get_side_buffer_offset(b, midpt, rack_segments)
                P_buf_cand = (midpt[0] + B_offset_cand * sdir[0], midpt[1] + B_offset_cand * sdir[1])
                # Check if P_buf_cand is inside the plot boundary (disabled since roads can ignore boundary)
                inside = True
                if inside:
                    valid_sides[side_name] = (midpt, sdir, P_buf_cand, B_offset_cand)

            # 2. Find the closest side to the core road network (road_segments) to determine orientation
            min_d = float('inf')
            close_side = "N"
            for side_name, (midpt, _) in sides.items():
                d = dist_to_road(midpt, road_segments) # Use core road_segments, not road_segments_p1
                if d < min_d:
                    min_d = d
                    close_side = side_name

            opp_map = {"N": "S", "S": "N", "E": "W", "W": "E"}
            opposite_side = opp_map[close_side]
            
            # If the ideal opposite side is invalid/blocked, fall back to the closest valid side to the core road network
            if opposite_side not in valid_sides:
                best_valid_side = None
                best_valid_dist = float('inf')
                for vside, (vmid, _, _, _) in valid_sides.items():
                    d = dist_to_road(vmid, road_segments)
                    if d < best_valid_dist:
                        best_valid_dist = d
                        best_valid_side = vside
                if best_valid_side is not None:
                    opposite_side = best_valid_side
            
            P_opp, opp_dir = sides[opposite_side]
            if opposite_side in valid_sides:
                B_offset = valid_sides[opposite_side][3]
            else:
                B_offset = get_side_buffer_offset(b, P_opp, rack_segments)
            
            if opposite_side == "N":
                C1 = (bx, by + bh + B_offset)
                C2 = (bx + bw, by + bh + B_offset)
            elif opposite_side == "S":
                C1 = (bx, by - B_offset)
                C2 = (bx + bw, by - B_offset)
            elif opposite_side == "E":
                C1 = (bx + bw + B_offset, by)
                C2 = (bx + bw + B_offset, by + bh)
            else:
                C1 = (bx - B_offset, by)
                C2 = (bx - B_offset, by + bh)
                
            P_buf = (P_opp[0] + B_offset * opp_dir[0], P_opp[1] + B_offset * opp_dir[1])
            
            # Path 1: Route from midpoint P_buf targeting road_cells_p1
            path1 = route_from_point(P_buf, road_segments_p1, road_cells_p1)
            
            # 1) Always strip path1[0] from Part 1 output.
            #    route_from_point always starts at P_buf's grid cell — we never want
            #    to draw the implicit block-buffer stub as a visible road segment.
            path1_spur_omitted = False
            path1_network_start_pt = None
            if path1 and len(path1) >= 2:
                path1_spur_omitted = True
                path1_network_start_pt = path1[0]  # shared start for Part 2 (= P_buf grid cell)
                path1 = path1[1:]
            
            def process_and_add_path(path, part_name="part1", align_end_to_segs=None):
                if not path:
                    return None
                # Deduplicate adjacent points (pre-snap)
                dedup = [path[0]]
                for p in path[1:]:
                    if math.hypot(p[0] - dedup[-1][0], p[1] - dedup[-1][1]) > 0.1:
                        dedup.append(p)
                path = dedup
                
                # Simplify collinear
                simplified = [path[0]]
                for idx in range(1, len(path)-1):
                    p0 = simplified[-1]
                    p1 = path[idx]
                    p2 = path[idx+1]
                    if not ((abs(p0[0] - p1[0]) < 0.1 and abs(p1[0] - p2[0]) < 0.1) or 
                            (abs(p0[1] - p1[1]) < 0.1 and abs(p1[1] - p2[1]) < 0.1)):
                        simplified.append(p1)
                simplified.append(path[-1])
                
                # Project last point onto the road network to close the terminal gap
                if align_end_to_segs and len(simplified) >= 2:
                    end_pt = simplified[-1]
                    prev_pt = simplified[-2]
                    aligned_end = align_terminal_to_network(end_pt, align_end_to_segs)
                    d_align = math.hypot(aligned_end[0] - end_pt[0], aligned_end[1] - end_pt[1])
                    if 0.1 < d_align < 16.0:  # only snap small gaps
                        # Moving the terminal PERPENDICULAR to the incoming leg
                        # would turn the last segment diagonal. Insert an
                        # orthogonal corner instead, then drop onto the network
                        # (straighten_arrival collapses the resulting short stub).
                        leg_horizontal = (abs(end_pt[1] - prev_pt[1]) < 0.1 and
                                          abs(end_pt[0] - prev_pt[0]) > 0.1)
                        leg_vertical = (abs(end_pt[0] - prev_pt[0]) < 0.1 and
                                        abs(end_pt[1] - prev_pt[1]) > 0.1)
                        if leg_horizontal and abs(aligned_end[1] - end_pt[1]) > 0.1:
                            simplified[-1] = (aligned_end[0], end_pt[1])  # corner
                            simplified.append(aligned_end)
                        elif leg_vertical and abs(aligned_end[0] - end_pt[0]) > 0.1:
                            simplified[-1] = (end_pt[0], aligned_end[1])  # corner
                            simplified.append(aligned_end)
                        else:
                            simplified[-1] = aligned_end
                
                # Snap to grid
                simplified_snapped = [(snap(x), snap(y)) for x, y in simplified]
                
                # Post-snap dedup: snap can collapse pre-snap distinct points to the same grid cell
                dedup2 = [simplified_snapped[0]]
                for p in simplified_snapped[1:]:
                    if math.hypot(p[0] - dedup2[-1][0], p[1] - dedup2[-1][1]) > 0.1:
                        dedup2.append(p)
                simplified_snapped = dedup2
                
                if len(simplified_snapped) >= 2:
                    access_roads.append(simplified_snapped)
                    access_roads_blocks.append(b_name)
                    access_roads_parts.append(part_name)
                    return simplified_snapped
                return None

            path1_snapped = process_and_add_path(path1, part_name="part1")
            
            # If the block is NOT inside the forbidden zone, also generate Path 2
            path2_snapped = None
            if not is_block_in_forbidden_zone(b, forbidden_zone_bbox):
                # Retrieve connection point
                path1_conn_pt = path1_snapped[-1] if path1_snapped else None
                if path1_conn_pt is None and path1 and len(path1) >= 1:
                    path1_conn_pt = path1[-1]
                
                # Corners of R
                R_left = bx - B_offset
                R_right = bx + bw + B_offset
                R_bottom = by - B_offset
                R_top = by + bh + B_offset
                
                V_se = (R_right, R_bottom)
                V_ne = (R_right, R_top)
                V_nw = (R_left, R_top)
                V_sw = (R_left, R_bottom)
                
                if opposite_side == "E":
                    seq_ccw = [V_ne, V_nw, V_sw, V_se, V_ne]
                    seq_cw  = [V_se, V_sw, V_nw, V_ne, V_se]
                elif opposite_side == "W":
                    seq_ccw = [V_sw, V_se, V_ne, V_nw, V_sw]
                    seq_cw  = [V_nw, V_ne, V_se, V_sw, V_nw]
                elif opposite_side == "N":
                    seq_ccw = [V_nw, V_sw, V_se, V_ne, V_nw]
                    seq_cw  = [V_ne, V_se, V_sw, V_nw, V_ne]
                else:  # "S"
                    seq_ccw = [V_se, V_ne, V_nw, V_sw, V_se]
                    seq_cw  = [V_sw, V_nw, V_ne, V_se, V_sw]
                    
                path_ccw = build_candidate_path(seq_ccw, P_buf, road_segments_all, path1_conn_pt)
                if not path_ccw:
                    path_ccw = fallback_connection(seq_ccw, P_buf, road_segments_all, road_cells_all, path1_conn_pt)
                    
                path_cw = build_candidate_path(seq_cw, P_buf, road_segments_all, path1_conn_pt)
                if not path_cw:
                    path_cw = fallback_connection(seq_cw, P_buf, road_segments_all, road_cells_all, path1_conn_pt)
                    
                # Evaluate candidates against No-Retrace rule
                ccw_ok = path_ccw and not check_overlap(path1_snapped, path_ccw, threshold=12.0, epsilon=5.0)
                cw_ok = path_cw and not check_overlap(path1_snapped, path_cw, threshold=12.0, epsilon=5.0)
                
                selected_path = None
                if ccw_ok and cw_ok:
                    # Choose shorter one
                    len_ccw = sum(math.hypot(path_ccw[i+1][0] - path_ccw[i][0], path_ccw[i+1][1] - path_ccw[i][1]) for i in range(len(path_ccw)-1))
                    len_cw = sum(math.hypot(path_cw[i+1][0] - path_cw[i][0], path_cw[i+1][1] - path_cw[i][1]) for i in range(len(path_cw)-1))
                    selected_path = path_ccw if len_ccw < len_cw else path_cw
                elif ccw_ok:
                    selected_path = path_ccw
                elif cw_ok:
                    selected_path = path_cw
                else:
                    # Fallback to shorter one
                    if path_ccw and path_cw:
                        len_ccw = sum(math.hypot(path_ccw[i+1][0] - path_ccw[i][0], path_ccw[i+1][1] - path_ccw[i][1]) for i in range(len(path_ccw)-1))
                        len_cw = sum(math.hypot(path_cw[i+1][0] - path_cw[i][0], path_cw[i+1][1] - path_cw[i][1]) for i in range(len(path_cw)-1))
                        selected_path = path_ccw if len_ccw < len_cw else path_cw
                    elif path_ccw:
                        selected_path = path_ccw
                    elif path_cw:
                        selected_path = path_cw
                        
                # Process Part 2 — project its last point onto the ring road to close any terminal gap
                if selected_path:
                    path2_snapped = process_and_add_path(selected_path, part_name="part2", align_end_to_segs=road_segments_p1)

                # Loop closure at the start: Part 1 and Part 2 must share their
                # start point (P_buf) and leave it as ONE straight line. The
                # spur strip removes path1[0], which is invisible in the normal
                # case (Part 1 resumes right at P_buf's grid cell) but detaches
                # the loop when Part 1's first hop heads away from the block
                # (e.g. hugging a slanted plot edge).
                if path1_snapped and path2_snapped and len(path2_snapped) >= 2:
                    shared_start = path2_snapped[0]  # = snapped P_buf
                    gap = math.hypot(shared_start[0] - path1_snapped[0][0],
                                     shared_start[1] - path1_snapped[0][1])
                    if 0.1 < gap < 16.0:
                        path1_snapped.insert(0, shared_start)  # in-place: access_roads holds this list

                    # Straighten Part 1's departure: A* can hug the outside of
                    # the block buffer, leaving a small parallel jog next to
                    # Part 2's line. Collapse the jog onto the line of Part 2's
                    # first segment so both parts run straight through the
                    # shared point.
                    starts_shared = math.hypot(shared_start[0] - path1_snapped[0][0],
                                               shared_start[1] - path1_snapped[0][1]) < 0.1
                    if starts_shared and len(path1_snapped) >= 2:
                        sx, sy = shared_start
                        nx, ny = path2_snapped[1]
                        vertical = abs(nx - sx) <= abs(ny - sy)  # Part 2 leaves along x=sx
                        jog_tol = float(B_offset)
                        k = 0
                        for p_idx in range(1, len(path1_snapped)):
                            px, py = path1_snapped[p_idx]
                            dev = abs(px - sx) if vertical else abs(py - sy)
                            if dev <= jog_tol:
                                k = p_idx
                            else:
                                break
                        if k >= 1:
                            kx, ky = path1_snapped[k]
                            straight_pt = (sx, ky) if vertical else (kx, sy)
                            new_p1 = [shared_start, straight_pt] + path1_snapped[k + 1:]
                            # If the straightening moved the terminal, re-project
                            # it onto the network (same rule as §3.7.B step 7)
                            if k == len(path1_snapped) - 1:
                                aligned = align_terminal_to_network(new_p1[-1], road_segments_p1)
                                d_align = math.hypot(aligned[0] - new_p1[-1][0], aligned[1] - new_p1[-1][1])
                                if 0.1 < d_align < 16.0:
                                    new_p1[-1] = (snap(aligned[0]), snap(aligned[1]))
                            dedup_p1 = [new_p1[0]]
                            for p in new_p1[1:]:
                                if math.hypot(p[0] - dedup_p1[-1][0], p[1] - dedup_p1[-1][1]) > 0.1:
                                    dedup_p1.append(p)
                            if len(dedup_p1) >= 2:
                                path1_snapped[:] = dedup_p1  # in-place: access_roads holds this list

            # Straighten arrivals so each part runs straight and turns only
            # once, at the network (§3.7.B step 7). Part 1 aligns against the
            # Part-1 network; Part 2 against the combined network plus this
            # block's own Part 1 (its terminal may legitimately land on either).
            if path1_snapped:
                straighten_arrival(path1_snapped, road_segments_p1, float(B_offset))
            if path2_snapped:
                p2_targets = list(road_segments_all)
                if path1_snapped and len(path1_snapped) >= 2:
                    p2_targets += [(path1_snapped[i], path1_snapped[i + 1])
                                   for i in range(len(path1_snapped) - 1)]
                straighten_arrival(path2_snapped, p2_targets, float(B_offset))

            # Polish (§3.7): no diagonal segments, minimal zigzag (L shapes)
            for _pp in (path1_snapped, path2_snapped):
                if _pp:
                    orthogonalize_path(_pp)
                    collapse_jogs(_pp)

            # §3.7 buffer-center rule: don't draw the perpendicular stub from
            # P_buf (the block's road-buffer center). If Part 1 leaves P_buf
            # ALONG opp_dir (perpendicular to the block side, pointing away
            # from the block) and then turns, drop that stub — the turn point
            # becomes the loop junction, and Part 2 is re-headed to start
            # there with an orthogonal connector.
            if (path1_snapped and path2_snapped and len(path1_snapped) >= 2
                    and len(path2_snapped) >= 2):
                _a0, _a1 = path1_snapped[0], path1_snapped[1]
                _ldx, _ldy = _a1[0] - _a0[0], _a1[1] - _a0[1]
                _stub_len = math.hypot(_ldx, _ldy)
                _along_opp = ((abs(opp_dir[0]) > 0 and abs(_ldy) < 0.1 and abs(_ldx) > 0.1) or
                              (abs(opp_dir[1]) > 0 and abs(_ldx) < 0.1 and abs(_ldy) > 0.1))
                _shared = (abs(_a0[0] - path2_snapped[0][0]) < 0.1 and
                           abs(_a0[1] - path2_snapped[0][1]) < 0.1)
                if _along_opp and _shared:
                    _junction = _a1
                    _q2 = path2_snapped[1]
                    if abs(opp_dir[0]) > 0:
                        _corner = (_junction[0], _q2[1])
                    else:
                        _corner = (_q2[0], _junction[1])
                    _new_head = [_junction]
                    if (math.hypot(_corner[0] - _junction[0], _corner[1] - _junction[1]) > 0.1
                            and math.hypot(_corner[0] - _q2[0], _corner[1] - _q2[1]) > 0.1):
                        _new_head.append(_corner)
                    _chk = _new_head + [_q2]
                    _head_ok = all(not segment_hits_footprint(_chk[_k], _chk[_k + 1])
                                   and not segment_near_rack(_chk[_k], _chk[_k + 1])
                                   for _k in range(len(_chk) - 1))
                    if _head_ok:
                        if len(path1_snapped) == 2:
                            # The ENTIRE Part 1 is the perpendicular stub
                            # (P_buf straight onto an existing road): draw
                            # nothing for Part 1 — its network end is the
                            # loop junction where Part 2 now starts.
                            for _ri in range(len(access_roads)):
                                if access_roads[_ri] is path1_snapped:
                                    del access_roads[_ri]
                                    del access_roads_blocks[_ri]
                                    del access_roads_parts[_ri]
                                    break
                            path1_snapped = None
                        else:
                            del path1_snapped[0]
                            _path_cleanup(path1_snapped)
                        path2_snapped[:1] = _new_head
                        _path_cleanup(path2_snapped)

            # Update networks
            if path1_snapped:
                add_path_to_road_network(path1_snapped, road_segments_p1, road_cells_p1)
                add_path_to_road_network(path1_snapped, road_segments_all, road_cells_all)
            if path2_snapped:
                add_path_to_road_network(path2_snapped, road_segments_all, road_cells_all)

        # -----------------------------------------------------------------
        # Step 11.5 — §3.7.E Part 3: trim at the temporary plot boundary
        # Roads are routed ignoring the boundary, so A* can excurse past a
        # slanted edge (e.g. a Part 2 loop around a block near the top edge).
        # Cleanup: cut every access-road centerline at the temporary (inset)
        # plot boundary and drop the outside portions. A road that crosses out
        # and back in splits into separate pieces; pieces shorter than 4 m are
        # discarded.
        # -----------------------------------------------------------------
        if plot is not None and access_roads:
            # Depth-based clipping (NOT edge-crossing based): a road can run
            # parallel to an edge slightly outside it and past a corner without
            # ever crossing an edge line — sample each segment ~every 1 m,
            # keep the runs where the signed depth >= -EDGE_TOL, and cut at
            # linearly interpolated boundary crossings.
            EDGE_TOL = 0.3  # grid-snapped roads may sit ~0.1-0.2 m outside the line

            def _lerp_pt(a, b, t):
                return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))

            _troads, _tblocks, _tparts = [], [], []
            for _road, _rb, _rp in zip(access_roads, access_roads_blocks, access_roads_parts):
                pieces = []
                curr = []
                for _i in range(len(_road) - 1):
                    _a, _b = _road[_i], _road[_i + 1]
                    _L = math.hypot(_b[0] - _a[0], _b[1] - _a[1])
                    _n = max(1, int(math.ceil(_L)))
                    _d_prev = plot.signed_dist_to_boundary(*_lerp_pt(_a, _b, 0.0))
                    for _k in range(1, _n + 1):
                        _t0, _t1 = (_k - 1) / _n, _k / _n
                        _d_now = plot.signed_dist_to_boundary(*_lerp_pt(_a, _b, _t1))
                        _in0 = _d_prev >= -EDGE_TOL
                        _in1 = _d_now >= -EDGE_TOL
                        if _in0 and _in1:
                            if not curr:
                                curr = [_lerp_pt(_a, _b, _t0)]
                            curr.append(_lerp_pt(_a, _b, _t1))
                        elif _in0 != _in1:
                            _den = _d_prev - _d_now
                            _tc = (_t0 + ((_d_prev + EDGE_TOL) / _den) * (_t1 - _t0)
                                   if abs(_den) > 1e-9 else _t0)
                            _tc = min(max(_tc, _t0), _t1)
                            _pcut = _lerp_pt(_a, _b, _tc)
                            if _in0:   # leaving the plot — close the piece
                                if not curr:
                                    curr = [_lerp_pt(_a, _b, _t0)]
                                curr.append(_pcut)
                                pieces.append(curr)
                                curr = []
                            else:      # entering the plot — open a piece
                                curr = [_pcut, _lerp_pt(_a, _b, _t1)]
                        _d_prev = _d_now
                if curr:
                    pieces.append(curr)
                for _pc in pieces:
                    # dedup + collinear simplify (sampling makes many 1 m points)
                    _dd = [_pc[0]]
                    for _q in _pc[1:]:
                        if math.hypot(_q[0] - _dd[-1][0], _q[1] - _dd[-1][1]) > 0.1:
                            _dd.append(_q)
                    # cross-product collinear removal (keep only real corners)
                    _out = [_dd[0]]
                    for _j in range(1, len(_dd) - 1):
                        _ux, _uy = _dd[_j][0] - _out[-1][0], _dd[_j][1] - _out[-1][1]
                        _vx, _vy = _dd[_j + 1][0] - _dd[_j][0], _dd[_j + 1][1] - _dd[_j][1]
                        if abs(_ux * _vy - _uy * _vx) > 1e-6:
                            _out.append(_dd[_j])
                    if len(_dd) >= 2:
                        _out.append(_dd[-1])
                    _plen = sum(math.hypot(_out[_j + 1][0] - _out[_j][0], _out[_j + 1][1] - _out[_j][1])
                                for _j in range(len(_out) - 1))
                    if len(_out) >= 2 and _plen >= 4.0:
                        _troads.append(_out)
                        _tblocks.append(_rb)
                        _tparts.append(_rp)
            access_roads = _troads
            access_roads_blocks = _tblocks
            access_roads_parts = _tparts

        # -----------------------------------------------------------------
        # Step 12 — Recenter output  [→ §3.8]
        # The recenter itself now runs pre-roads (Step 10.9). Here we simply
        # emit the current plot/gate/spur/death-zone — already recentered if
        # Step 10.9 applied, otherwise untouched. The `*_before` snapshots and
        # `recenter_delta` were captured/set by Step 10.9.
        # -----------------------------------------------------------------
        _dx, _dy = recenter_delta
        if plot is not None:
            plot_bounds = (plot.bbox[0], plot.bbox[1], plot.size[0], plot.size[1])
            plot_polygon_out = list(plot.vertices)
        else:
            plot_bounds = (0.0, 0.0, sw, sl)
            plot_polygon_out = None
        gate_pt_rec = gate_pt
        gate_spur_rec = list(gate_road_out) if gate_road_out else gate_spur
        gate_death_zone_rec = gate_death_zone

        _last_debug["failed_at"] = None
        _last_debug["failed_section"] = None
        _last_debug["boundary_tol_used"] = _pass_tol
        _last_debug["boundary_pass_label"] = _pass_label
        _last_debug["recenter_delta"] = recenter_delta

        return {
            "blocks":          blocks,
            "boom_barrier":    boom_out if boom_out else [],
            "ring_road":       ring_road,
            "gate_spur":       gate_spur_rec,
            "ring_spur":       ring_spur_out if ring_spur_out else ring_spur,
            "gate_death_zone": gate_death_zone_rec,
            "gate_point":      gate_pt_rec,
            "gate_point_before": gate_pt_before,
            "pb_center":       (pb_cx, pb_cy),
            "rack_buffers":    rack_buffers,
            "rack_segments":   rack_segments,
            "spine_centerlines": spine_centerlines,
            "pb_buffer_hits":  pb_buffer_hits,
            "main_rack_output": main_rack_output,
            "water_cluster_segments": water_cluster_segments,
            "pruned_rack_segments": pruned_rack_segments,
            "water_triangle":  water_triangle,
            "rack_candidates": candidate_points,
            "active_rack_cases": active_cases,
            "plot_polygon":    plot_polygon_out,
            "plot_polygon_original": list(plot.original_plot.vertices) if getattr(plot, "original_plot", None) is not None else None,
            "plot_polygon_before": plot_polygon_before,
            "plot_polygon_original_before": plot_polygon_original_before,
            "plot_bounds":     plot_bounds,
            "plot_bounds_before": plot_bounds_before,
            "recenter_delta":  recenter_delta,
            "blocks_only":     True,
            "cell_size":       CELL_SIZE,
            "boundary_tol_used":   _pass_tol,
            "boundary_pass_label": _pass_label,
            "access_roads":    access_roads,
            "access_roads_blocks": access_roads_blocks,
            "access_roads_parts": access_roads_parts,
            "perimeter_segments_raw": [],
            "group_a_segments_raw": [],
            "all_segments_cleaned": [],
            "outer_loop":      [],
            "outer_loop_pts":  [],
            "computed_buffers_debug": computed_buffers if 'computed_buffers' in locals() else {},
        }
        # Inner loop (max_pool) exhausted without finding a layout for this pass.
        # Fall through to the next pass (relaxed tolerance).

    return None

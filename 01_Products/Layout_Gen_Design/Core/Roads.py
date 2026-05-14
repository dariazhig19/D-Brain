"""Road infrastructure for PowerPlan AI layouts.

Owns the geometry and dimensional constants for the perimeter fire road and
the spacing rules between roads, buildings, and racks. Two road builders
coexist:

* :func:`build_perimeter_road` + :func:`deform_around_buildings` — rectangular
  ring with rectangular bulges (Phase 05 step 2; only handles the north edge).
* :func:`build_road_network` — grid-based A* routing that handles all four
  edges naturally and produces a smooth closed loop around any number of
  intruding buildings.
"""

from Core.Grid import Grid
from Core.Pathfind import astar


# ── Constants (metres) ────────────────────────────────────────────────────

ROAD_WIDTH       = 7      # All roads are 7m wide
ROAD_SETBACK     = 5      # Perimeter road outer edge is 5m from site boundary
ROAD_TO_BUILDING = 3      # Min gap from road inner edge to building
ROAD_TO_RACK     = 2      # Min gap from road to rack
RACK_TO_BLOCK    = 2.5    # Min gap from rack to building

# Inner edge of perimeter road = ROAD_SETBACK + ROAD_WIDTH = 12m from boundary
ROAD_INNER_EDGE  = ROAD_SETBACK + ROAD_WIDTH

# Minimum building distance from boundary = road inner edge + gap = 15m
MIN_BUILDING_FROM_BOUNDARY = ROAD_INNER_EDGE + ROAD_TO_BUILDING


# ── Geometry ──────────────────────────────────────────────────────────────

def build_perimeter_road(site_w, site_l, setback=ROAD_SETBACK, width=ROAD_WIDTH):
    """Return the outer and inner edge rectangles of the perimeter fire road.

    Returns:
        dict with keys:
            'outer'   — list of (x, y) corners, road outer edge (= setback from boundary)
            'inner'   — list of (x, y) corners, road inner edge (= setback + width)
            'setback' — outer-edge distance from boundary
            'width'   — road width
    """
    outer = [
        (setback,          setback),
        (site_w - setback, setback),
        (site_w - setback, site_l - setback),
        (setback,          site_l - setback),
    ]
    inner_offset = setback + width
    inner = [
        (inner_offset,          inner_offset),
        (site_w - inner_offset, inner_offset),
        (site_w - inner_offset, site_l - inner_offset),
        (inner_offset,          site_l - inner_offset),
    ]
    return {"outer": outer, "inner": inner, "setback": setback, "width": width}


# ── Deformation ───────────────────────────────────────────────────────────

def _intrudes_top(b, inner_top_y):
    """Building intrudes the top edge if its top extends above the road inner edge."""
    return b["y"] + b["height"] > inner_top_y


def deform_around_buildings(road, buildings, site_w, site_l, gap=ROAD_TO_BUILDING):
    """Bend the perimeter road inward where buildings push into its corridor.

    Phase 05 step 2 (minimal): only handles the NORTH (top) edge. Buildings on
    other edges are ignored for now even if they intrude. The returned road
    keeps `outer`/`inner` corner rectangles unchanged and adds two new keys —
    `outer_polyline` and `inner_polyline` — as closed CCW point lists that
    callers (visualization, scoring) should prefer.

    When no buildings intrude, the polylines equal the original rectangles.
    """
    setback = road["setback"]
    width   = road["width"]

    inner_top_y = site_l - setback - width   # original inner-edge y on north
    outer_top_y = site_l - setback           # original outer-edge y on north

    # Find intruders on the top edge, sorted left-to-right
    intruders = sorted(
        (b for b in buildings if _intrudes_top(b, inner_top_y)),
        key=lambda b: b["x"],
    )

    # Build top-edge polylines (left-to-right) with rectangular bulges
    top_inner_pts = [(setback + width, inner_top_y)]
    top_outer_pts = [(setback,         outer_top_y)]
    for b in intruders:
        bx, by, bw, bh = b["x"], b["y"], b["width"], b["height"]
        bx_left  = max(setback + width, bx - gap)
        bx_right = min(site_w - setback - width, bx + bw + gap)
        # On the top edge, the road's OUTER edge sits closer to the boundary
        # (higher y) and is what must clear the building by `gap`. The inner
        # edge follows it `width` further south. The whole road shifts together.
        bulge_outer_y = max(0.0, by - gap)
        bulge_inner_y = bulge_outer_y - width
        top_inner_pts += [
            (bx_left,  inner_top_y),
            (bx_left,  bulge_inner_y),
            (bx_right, bulge_inner_y),
            (bx_right, inner_top_y),
        ]
        top_outer_pts += [
            (bx_left,  outer_top_y),
            (bx_left,  bulge_outer_y),
            (bx_right, bulge_outer_y),
            (bx_right, outer_top_y),
        ]
    top_inner_pts.append((site_w - setback - width, inner_top_y))
    top_outer_pts.append((site_w - setback,         outer_top_y))

    # Assemble closed CCW loops. Other 3 edges stay rectangular.
    outer_polyline = (
        [(setback, setback), (site_w - setback, setback)]
        + list(reversed(top_outer_pts))
        + [(setback, setback)]
    )
    inner_polyline = (
        [(setback + width, setback + width),
         (site_w - setback - width, setback + width)]
        + list(reversed(top_inner_pts))
        + [(setback + width, setback + width)]
    )

    return {**road, "outer_polyline": outer_polyline, "inner_polyline": inner_polyline}


# ── Grid-based A* road network ────────────────────────────────────────────

def _ring_waypoints(grid, margin_m, n_per_edge):
    """Sample ``n_per_edge`` cell waypoints along each side of a rectangle
    that sits just inside the setback ring. Returns a clockwise list.

    Waypoints are pushed one cell inside the setback so they are guaranteed
    to satisfy the width-aware passability check during A*.
    """
    cs = grid.cell_size
    # World coords of the inner-setback rectangle, pulled in by one cell so
    # the (2*width+1) corridor around each waypoint stays inside the grid.
    x0 = margin_m + cs
    y0 = margin_m + cs
    x1 = grid.site_w - margin_m - cs
    y1 = grid.site_l - margin_m - cs

    def lerp(a, b, t):
        return a + (b - a) * t

    pts = []
    for k in range(n_per_edge):   # bottom edge L→R
        t = k / n_per_edge
        pts.append((lerp(x0, x1, t), y0))
    for k in range(n_per_edge):   # right edge B→T
        t = k / n_per_edge
        pts.append((x1, lerp(y0, y1, t)))
    for k in range(n_per_edge):   # top edge R→L
        t = k / n_per_edge
        pts.append((lerp(x1, x0, t), y1))
    for k in range(n_per_edge):   # left edge T→B
        t = k / n_per_edge
        pts.append((x0, lerp(y1, y0, t)))

    return [grid.world_to_cell(x, y) for (x, y) in pts]


def build_road_network(site_w, site_l, buildings, *,
                       cell_size=2.5,
                       n_per_edge=6,
                       turn_penalty=0.5,
                       width_cells=1):
    """Construct a closed-loop perimeter road by A* on an occupancy grid.

    Builds a :class:`Grid`, blocks buildings (inflated by ``ROAD_TO_BUILDING``)
    and the setback strip, then routes the road between waypoints arranged
    around the inside of the setback ring. The concatenated path forms a
    closed loop that deforms inward around any building that intrudes — and
    handles all four edges uniformly, unlike :func:`deform_around_buildings`.

    Args:
        site_w, site_l: site dimensions in metres.
        buildings:      iterable of dicts with ``x``, ``y``, ``width``, ``height``.
        cell_size:      grid resolution in metres (default 2.5).
        n_per_edge:     waypoints per side of the loop (default 6 → 24 total).
        turn_penalty:   smoothing prior passed to :func:`astar`.
        width_cells:    half-width of required clear corridor. ``1`` ⇒ 3-cell
                        corridor ≈ 7.5 m, slightly above the 7 m road spec.

    Returns:
        Dict with the same shape as :func:`build_perimeter_road` plus:
            ``loop_cells``  list of (i, j) cell indices, closed
            ``loop_world``  list of (x, y) world coords, closed
            ``grid``        the occupancy Grid (reusable by rack routing)
            ``mode``        ``'astar'``
        Returns ``None`` if any segment fails to find a path.
    """
    grid = Grid(site_w, site_l, cell_size=cell_size)
    grid.mark_buildings(buildings, inflate_m=ROAD_TO_BUILDING)
    grid.mark_setback(ROAD_SETBACK)

    waypoints = _ring_waypoints(grid, ROAD_SETBACK, n_per_edge)

    loop_cells = []
    for k in range(len(waypoints)):
        a = waypoints[k]
        b = waypoints[(k + 1) % len(waypoints)]
        segment = astar(grid, a, b,
                        turn_penalty=turn_penalty,
                        width_cells=width_cells)
        if segment is None:
            return None
        # Drop the segment's last cell — next segment's first cell repeats it.
        loop_cells.extend(segment[:-1] if k < len(waypoints) - 1 else segment)

    loop_world = [grid.cell_to_world(i, j) for (i, j) in loop_cells]

    return {
        "outer":         None,
        "inner":         None,
        "setback":       ROAD_SETBACK,
        "width":         ROAD_WIDTH,
        "loop_cells":    loop_cells,
        "loop_world":    loop_world,
        "grid":          grid,
        "mode":          "astar",
    }

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
from Core.Pathfind import astar, snap_to_passable, build_passable


# ── Constants (metres) ────────────────────────────────────────────────────

ROAD_WIDTH       = 8      # All roads are 7m wide
ROAD_SETBACK     = 5      # Perimeter road outer edge is 5m from site boundary
ROAD_TO_BUILDING = 6      # Min gap from road inner edge to building
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


# ── Grid-based A* internal road network ───────────────────────────────────

def build_road_network(site_w, site_l, buildings, gate_point, *,
                       cell_size=1.0,
                       turn_penalty=0.5):
    """Build an internal road network connecting the site gate to all
    building entrances via A* on an occupancy grid.

    Buildings are marked on the grid with a 6m inflation buffer
    (``ROAD_TO_BUILDING``). A* runs with ``width_cells=4`` to enforce
    a physical 9-cell (9m) road footprint.

    Args:
        site_w, site_l: site dimensions in metres.
        buildings:      iterable of group dicts with ``x``, ``y``, ``width``,
                        ``height``, and ``entrance_points``.
        gate_point:     (x, y) world coordinate of the site gate on the boundary.
        cell_size:      grid resolution in metres (default 2.5).
        turn_penalty:   smoothing prior passed to :func:`astar`.

    Returns:
        Dict with:
            ``segments``    list of dicts, each with ``from``, ``to``, ``path_world``
            ``grid``        the occupancy Grid
            ``mode``        ``'internal'``
        Returns ``None`` if any entrance is unreachable from the gate.
    """
    grid = Grid(site_w, site_l, cell_size=cell_size)
    grid.mark_buildings(buildings, inflate_m=ROAD_TO_BUILDING)

    # Erodes the free space to ensure a 9m wide road footprint (9 cells) fits.
    width_cells = 4
    passable = build_passable(grid, width_cells)

    gate_cell = grid.world_to_cell(*gate_point)
    # Snap gate to nearest passable cell if it landed in a blocked zone
    gate_cell = snap_to_passable(passable, gate_cell, max_radius=30)
    if gate_cell is None:
        return None

    segments = []

    for building in buildings:
        for entrance_pt in building.get("entrance_points", []):
            ent_cell = grid.world_to_cell(*entrance_pt)
            # Snap entrance to nearest passable cell
            ent_cell = snap_to_passable(passable, ent_cell, max_radius=15)
            if ent_cell is None:
                return None

            path = astar(grid, gate_cell, ent_cell,
                         turn_penalty=turn_penalty,
                         width_cells=width_cells,
                         passable=passable)
            if path is None:
                return None

            path_world = [grid.cell_to_world(i, j) for (i, j) in path]
            segments.append({
                "from":       "gate",
                "to":         building["name"],
                "to_point":   entrance_pt,
                "path_cells": path,
                "path_world": path_world,
            })

    return {
        "segments":    segments,
        "grid":        grid,
        "mode":        "internal",
        "width":       ROAD_WIDTH,
        "width_cells": width_cells,
    }

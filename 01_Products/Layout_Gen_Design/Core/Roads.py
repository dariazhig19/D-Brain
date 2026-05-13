"""Road infrastructure for PowerPlan AI layouts.

Owns the geometry and dimensional constants for the perimeter fire road and
the spacing rules between roads, buildings, and racks. Phase 05 ships only
the rectangular perimeter ring; later phases will add deformation around
buildings and internal connector roads.
"""

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

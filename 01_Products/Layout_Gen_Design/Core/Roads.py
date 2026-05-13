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
        bulge_inner_y = max(0.0, by - gap)        # how deep the road dips
        bulge_outer_y = bulge_inner_y + width     # road keeps its width
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

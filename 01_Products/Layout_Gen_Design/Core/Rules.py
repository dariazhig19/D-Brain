import math

# ROAD_INNER_EDGE: setback of perimeter fire road inner edge from boundary
# Stage01 has 5m setback + 8m road width = 13m
ROAD_INNER_EDGE = 13

# ── Helpers ────────────────────────────────────────────────────────────────

def _center(group):
    """Return (cx, cy) of a group rectangle."""
    return group["x"] + group["width"] / 2, group["y"] + group["height"] / 2


def _edge_distance(group, site_width, site_length, plot=None):
    """Minimum distance from any edge of the group rect to any site boundary."""
    if plot is not None:
        x, y, w, h = group["x"], group["y"], group["width"], group["height"]
        corners = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        return min(plot.signed_dist_to_boundary(cx, cy) for cx, cy in corners)
    x, y, w, h = group["x"], group["y"], group["width"], group["height"]
    return min(x, y, site_width - (x + w), site_length - (y + h))


def _dist(cx1, cy1, cx2, cy2):
    return math.sqrt((cx1 - cx2) ** 2 + (cy1 - cy2) ** 2)


def _closest_edge(group, site_width, site_length, plot=None):
    """Return (edge_name, distance) for the closest site boundary."""
    if plot is not None:
        x, y, w, h = group["x"], group["y"], group["width"], group["height"]
        corners = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        min_d = 99999.0
        best_idx = 0
        for cx, cy in corners:
            for i, e in enumerate(plot.edges):
                d = plot._edge_signed_dist(e, cx, cy)
                if d < min_d:
                    min_d = d
                    best_idx = i
        return f"Edge {best_idx}", min_d
    
    x, y, w, h = group["x"], group["y"], group["width"], group["height"]
    edges = {
        "left":   x,
        "bottom": y,
        "right":  site_width  - (x + w),
        "top":    site_length - (y + h),
    }
    name = min(edges, key=edges.get)
    return name, edges[name]


def _get_bbox_distances(group, plot, site_width=None, site_length=None):
    if plot is not None:
        minx, miny, maxx, maxy = plot.bbox
    else:
        minx, miny, maxx, maxy = 0.0, 0.0, site_width, site_length
    x, y, w, h = group["x"], group["y"], group["width"], group["height"]
    return {
        "East":  maxx - (x + w),
        "West":  x - minx,
        "North": maxy - (y + h),
        "South": y - miny,
        "width": maxx - minx,
        "length": maxy - miny,
    }


def _point_to_line_dist(px, py, x1, y1, x2, y2):
    """Minimum distance from point (px,py) to line segment (x1,y1)-(x2,y2)."""
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return _dist(px, py, x1, y1)
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    proj_x, proj_y = x1 + t * dx, y1 + t * dy
    return _dist(px, py, proj_x, proj_y)


def _rect_edge_distance(g1, g2):
    """Minimum edge-to-edge distance between two rectangles.
    Returns 0 if they overlap.
    """
    x1, y1, w1, h1 = g1["x"], g1["y"], g1["width"], g1["height"]
    x2, y2, w2, h2 = g2["x"], g2["y"], g2["width"], g2["height"]

    # Separation on each axis (negative = overlap on that axis)
    dx = max(0, max(x1 - (x2 + w2), x2 - (x1 + w1)))
    dy = max(0, max(y1 - (y2 + h2), y2 - (y1 + h1)))

    if dx == 0 and dy == 0:
        return 0.0  # overlapping or touching
    return math.sqrt(dx * dx + dy * dy)


def _point_to_rect_distance(px, py, group):
    """Shortest distance from a point to the closest edge of a rectangle.
    Returns 0 if the point lies inside the rectangle.
    """
    x, y, w, h = group["x"], group["y"], group["width"], group["height"]
    dx = max(x - px, 0, px - (x + w))
    dy = max(y - py, 0, py - (y + h))
    return math.sqrt(dx * dx + dy * dy)


def _result(id_, name, group, passed, penalty, message, measured, threshold, calc):
    """Standardized rule result dict."""
    return {
        "id":        id_,
        "name":      name,
        "group":     group,
        "passed":    passed,
        "penalty":   round(penalty, 1),
        "message":   message,
        "measured":  measured,   # actual measured value (with unit label)
        "threshold": threshold,  # constraint limit (with unit label)
        "calc":      calc,       # human-readable penalty calculation string
    }


# ── Evaluator functions ───────────────────────────────────────────────────

def _eval_center_proximity(rule, group, site_width, site_length, plot=None, **_):
    cx, cy = _center(group)
    if plot is not None:
        site_cx, site_cy = plot.centroid
    else:
        site_cx, site_cy = site_width / 2, site_length / 2
    distance = _dist(cx, cy, site_cx, site_cy)
    excess = max(0.0, distance - rule["threshold"])
    penalty = excess * rule["penalty_rate"]
    passed = excess == 0
    return _result(
        rule["id"], f"{rule['group']}: Center (±{rule['threshold']} m)", rule["group"],
        passed, penalty,
        f"Within tolerance ✓ ({distance:.1f} m)" if passed else f"Off-center by {excess:.1f} m",
        measured=f"{distance:.1f} m from plot center",
        threshold=f"≤ {rule['threshold']} m",
        calc=f"{excess:.1f} m × {rule['penalty_rate']} pts/m = {penalty:,.0f} pts" if excess > 0 else "0 pts (OK)",
    )


def _eval_center_proximity_asymmetric(rule, group, site_width, site_length, wind_dir="East", plot=None, **_):
    cx, cy = _center(group)
    if plot is not None:
        site_cx, site_cy = plot.centroid
        minx, miny, maxx, maxy = plot.bbox
        w_size, l_size = maxx - minx, maxy - miny
    else:
        site_cx, site_cy = site_width / 2, site_length / 2
        w_size, l_size = site_width, site_length
    dx = cx - site_cx
    dy = cy - site_cy

    wind_tol = {
        "East":  {"pos_x": w_size * 0.35, "neg_x": w_size * 0.05,
                  "pos_y": l_size * 0.20, "neg_y": l_size * 0.20},
        "West":  {"pos_x": w_size * 0.05, "neg_x": w_size * 0.35,
                  "pos_y": l_size * 0.20, "neg_y": l_size * 0.20},
        "North": {"pos_x": w_size * 0.20, "neg_x": w_size * 0.20,
                  "pos_y": l_size * 0.35, "neg_y": l_size * 0.05},
        "South": {"pos_x": w_size * 0.20, "neg_x": w_size * 0.20,
                  "pos_y": l_size * 0.05, "neg_y": l_size * 0.35},
    }
    tol = wind_tol.get(wind_dir, wind_tol["East"])

    excess_x = max(0.0, dx - tol["pos_x"]) if dx >= 0 else max(0.0, -dx - tol["neg_x"])
    excess_y = max(0.0, dy - tol["pos_y"]) if dy >= 0 else max(0.0, -dy - tol["neg_y"])

    excess  = (excess_x ** 2 + excess_y ** 2) ** 0.5
    penalty = excess * rule["penalty_rate"]
    passed  = excess == 0.0

    measured  = f"{dx:+.1f} m (x), {dy:+.1f} m (y) from plot center (wind={wind_dir})"
    threshold = (
        f"x: −{tol['neg_x']:.0f} m … +{tol['pos_x']:.0f} m  "
        f"y: −{tol['neg_y']:.0f} m … +{tol['pos_y']:.0f} m"
    )
    calc = (
        f"Excess: √({excess_x:.1f}²+{excess_y:.1f}²) = {excess:.1f} m × {rule['penalty_rate']} pts/m = {penalty:,.0f} pts"
        if excess > 0 else "0 pts (within asymmetric window)"
    )
    return _result(
        rule["id"],
        f"{rule['group']}: Asymmetric center proximity (wind={wind_dir})",
        rule["group"],
        passed,
        penalty,
        f"Within window ✓ ({dx:+.1f} m, {dy:+.1f} m)" if passed else f"Outside window by {excess:.1f} m",
        measured,
        threshold,
        calc,
    )


def _eval_boundary_setback(rule, group, site_width, site_length, plot=None, **_):
    edge_name, edge_val = _closest_edge(group, site_width, site_length, plot=plot)
    violated = edge_val < rule["threshold"]
    penalty = rule["penalty_rate"] if violated else 0
    return _result(
        rule["id"], f"{rule['group']}: Setback ({rule['threshold']} m)", rule["group"],
        not violated, penalty,
        f"Too close to {edge_name}: {edge_val:.1f} m" if violated else f"All edges ≥ {rule['threshold']} m ✓",
        measured=f"Closest edge ({edge_name}): {edge_val:.1f} m",
        threshold=f"≥ {rule['threshold']} m on all sides",
        calc=f"{rule['penalty_rate']:,} pts flat (violation)" if violated else "0 pts (OK)",
    )


def _eval_windward_edge(rule, group, site_width, site_length, wind_dir, plot=None, **_):
    dists = _get_bbox_distances(group, plot, site_width, site_length)
    dist_to_edge = dists[wind_dir]
    on_edge = dist_to_edge <= rule["threshold"]
    penalty = 0 if on_edge else rule["penalty_rate"]
    edge_label = f"{wind_dir} windward edge"
    return _result(
        rule["id"], f"{rule['group']}: Windward Edge", rule["group"],
        on_edge, penalty,
        f"On {wind_dir} windward edge ✓" if on_edge else f"Not on {wind_dir} windward edge",
        measured=f"Distance to {edge_label}: {dist_to_edge:.1f} m",
        threshold=f"≤ {rule['threshold']} m from {edge_label} (wind = {wind_dir})",
        calc="0 pts (on edge)" if on_edge else f"{rule['penalty_rate']:,} pts flat (not on windward edge)",
    )


def _eval_leeward_edge(rule, group, site_width, site_length, wind_dir, plot=None, **_):
    dists = _get_bbox_distances(group, plot, site_width, site_length)
    opp_wind = {"East": "West", "West": "East", "North": "South", "South": "North"}[wind_dir]
    dist_to_edge = dists[opp_wind]
    on_edge = dist_to_edge <= rule["threshold"]
    penalty = 0 if on_edge else rule["penalty_rate"]
    edge_label = f"{opp_wind} leeward edge (downwind)"
    return _result(
        rule["id"], f"{rule['group']}: Leeward Edge (Downwind)", rule["group"],
        on_edge, penalty,
        f"On downwind ({wind_dir} leeward) edge" if on_edge else f"Not on downwind edge",
        measured=f"Distance to {edge_label}: {dist_to_edge:.1f} m",
        threshold=f"<= {rule['threshold']} m from {edge_label} (wind = {wind_dir})",
        calc="0 pts (on edge)" if on_edge else f"{rule['penalty_rate']:,} pts flat (not on downwind edge)",
    )


def _eval_min_distance(rule, group, target_group, **_):
    cx1, cy1 = _center(group)
    cx2, cy2 = _center(target_group)
    distance = _dist(cx1, cy1, cx2, cy2)
    shortfall = max(0.0, rule["threshold"] - distance)
    penalty = shortfall * rule["penalty_rate"]
    return _result(
        rule["id"], f"{rule['group']} ↔ {rule['target']}: Min Dist", rule["group"],
        shortfall == 0, penalty,
        f"{distance:.1f} m ✓" if shortfall == 0 else f"Too close: {distance:.1f} m (need ≥ {rule['threshold']} m)",
        measured=f"{distance:.1f} m center-to-center",
        threshold=f"≥ {rule['threshold']} m",
        calc=f"Shortfall: {rule['threshold']} − {distance:.1f} = {shortfall:.1f} m × {rule['penalty_rate']} pts/m = {penalty:,.0f} pts" if shortfall > 0 else "0 pts (OK)",
    )


def _eval_max_distance(rule, group, target_group, **_):
    cx1, cy1 = _center(group)
    cx2, cy2 = _center(target_group)
    distance = _dist(cx1, cy1, cx2, cy2)
    excess = max(0.0, distance - rule["threshold"])
    penalty = excess * rule["penalty_rate"]
    return _result(
        rule["id"], f"{rule['group']} ↔ {rule['target']}: Max Dist", rule["group"],
        excess == 0, penalty,
        f"{distance:.1f} m ✓" if excess == 0 else f"Too far: {distance:.1f} m (need ≤ {rule['threshold']} m)",
        measured=f"{distance:.1f} m center-to-center",
        threshold=f"≤ {rule['threshold']} m",
        calc=f"Excess: {distance:.1f} − {rule['threshold']} = {excess:.1f} m × {rule['penalty_rate']} pts/m = {penalty:,.0f} pts" if excess > 0 else "0 pts (OK)",
    )


def _eval_rack_length(rule, group, target_group, **_):
    distance = _rect_edge_distance(group, target_group)
    penalty = distance * rule["penalty_rate"]
    rack_name = rule.get("rack", "Rack")
    return _result(
        rule["id"],
        f"{rack_name}: {rule['group']} ↔ {rule['target']}",
        rack_name,
        distance == 0, penalty,
        f"Edge-to-edge: {distance:.1f} m" if distance > 0 else "Adjacent (0 m)",
        measured=f"{distance:.1f} m edge-to-edge",
        threshold="0 m (as short as possible)",
        calc=f"{distance:.1f} m × {rule['penalty_rate']} pts/m = {penalty:,.0f} pts" if distance > 0 else "0 pts (adjacent)",
    )


def _eval_road_proximity(rule, group, site_width, site_length, plot=None, **_):
    if plot is not None:
        edge_val = min(plot.signed_dist_to_boundary(cx, cy) for cx, cy in [
            (group["x"], group["y"]),
            (group["x"] + group["width"], group["y"]),
            (group["x"] + group["width"], group["y"] + group["height"]),
            (group["x"], group["y"] + group["height"])
        ])
        edge_name = "boundary"
        road_inner = ROAD_INNER_EDGE
    else:
        edge_name, edge_val = _closest_edge(group, site_width, site_length)
        road_inner = 12.0 # legacy setback (5) + road width (7)
    
    min_dist = edge_val - road_inner
    shortfall = max(0.0, rule["threshold"] - min_dist)
    penalty = shortfall * rule["penalty_rate"]
    passed = shortfall == 0
    return _result(
        rule["id"], f"{rule['group']}: Road Gap", rule["group"],
        passed, penalty,
        f"Road gap OK ({min_dist:.1f} m from {edge_name} road) ✓" if passed else f"Too close to {edge_name} road: {min_dist:.1f} m (need ≥ {rule['threshold']} m)",
        measured=f"Closest road edge: {min_dist:.1f} m",
        threshold=f"≥ {rule['threshold']} m from road inner edge",
        calc=f"Shortfall: {rule['threshold']} − {min_dist:.1f} = {shortfall:.1f} m × {rule['penalty_rate']} pts/m = {penalty:,.0f} pts" if shortfall > 0 else "0 pts (OK)",
    )


def _eval_boundary_overflow(rule, group, site_width, site_length, plot=None, **_):
    if plot is not None:
        x, y, w, h = group["x"], group["y"], group["width"], group["height"]
        corners = [(x, y), (x+w, y), (x+w, y+h), (x, y+h)]
        total_overflow = sum(max(0.0, -plot.signed_dist_to_boundary(cx, cy)) for cx, cy in corners)
    else:
        x, y, w, h = group["x"], group["y"], group["width"], group["height"]
        overflow_left   = max(0.0, -x)
        overflow_bottom = max(0.0, -y)
        overflow_right  = max(0.0, (x + w) - site_width)
        overflow_top    = max(0.0, (y + h) - site_length)
        total_overflow  = overflow_left + overflow_bottom + overflow_right + overflow_top

    if total_overflow > 0:
        penalty = rule["penalty_rate"] * math.log(1 + total_overflow)
    else:
        penalty = 0

    passed = total_overflow == 0
    return _result(
        rule["id"], f"{rule['group']}: Boundary Overflow", rule["group"],
        passed, penalty,
        f"Within boundaries ✓" if passed else f"Overflows boundary by {total_overflow:.1f} m total",
        measured=f"Total overflow: {total_overflow:.1f} m",
        threshold="0 m (should stay within boundary)",
        calc=f"{rule['penalty_rate']} × ln(1 + {total_overflow:.1f}) = {penalty:,.0f} pts" if total_overflow > 0 else "0 pts (OK)",
    )


def _eval_gate_distance(rule, group, gate_point, **_):
    if gate_point is None:
        return _result(
            rule["id"], f"{rule['group']} ↔ {rule['target']}: Min Dist", rule["group"],
            True, 0,
            "Skipped (no gate_point supplied)",
            measured="n/a", threshold=f"≥ {rule['threshold']} m", calc="0 pts (skipped)",
        )
    gx, gy = gate_point
    distance = _point_to_rect_distance(gx, gy, group)
    shortfall = max(0.0, rule["threshold"] - distance)
    penalty = shortfall * rule["penalty_rate"]
    passed = shortfall == 0
    return _result(
        rule["id"], f"{rule['group']} ↔ {rule['target']}: Min Dist", rule["group"],
        passed, penalty,
        f"{distance:.1f} m from gate ✓" if passed else f"Too close to gate: {distance:.1f} m (need ≥ {rule['threshold']} m)",
        measured=f"{distance:.1f} m (edge-to-point)",
        threshold=f"≥ {rule['threshold']} m from gate",
        calc=f"Shortfall: {rule['threshold']} − {distance:.1f} = {shortfall:.1f} m × {rule['penalty_rate']} pts/m = {penalty:,.0f} pts" if shortfall > 0 else "0 pts (OK)",
    )


def _eval_max_gate_distance(rule, group, gate_point, **_):
    if gate_point is None:
        return _result(
            rule["id"], f"{rule['group']} ↔ {rule['target']}: Max Dist", rule["group"],
            True, 0,
            "Skipped (no gate_point supplied)",
            measured="n/a", threshold=f"≤ {rule['threshold']} m", calc="0 pts (skipped)",
        )
    gx, gy = gate_point
    distance = _point_to_rect_distance(gx, gy, group)
    excess = max(0.0, distance - rule["threshold"])
    penalty = excess * rule["penalty_rate"]
    passed = excess == 0
    return _result(
        rule["id"], f"{rule['group']} ↔ {rule['target']}: Max Dist", rule["group"],
        passed, penalty,
        f"{distance:.1f} m from gate ✓" if passed else f"Too far from gate: {distance:.1f} m (need ≤ {rule['threshold']} m)",
        measured=f"{distance:.1f} m (edge-to-point)",
        threshold=f"≤ {rule['threshold']} m from gate",
        calc=f"Excess: {distance:.1f} − {rule['threshold']} = {excess:.1f} m × {rule['penalty_rate']} pts/m = {penalty:,.0f} pts" if excess > 0 else "0 pts (OK)",
    )


def _eval_parallel_to_short_edge(rule, group, site_width, site_length, plot=None, **_):
    w, h = group["width"], group["height"]
    is_square = (w == h)
    if plot is not None:
        minx, miny, maxx, maxy = plot.bbox
        p_w, p_l = maxx - minx, maxy - miny
    else:
        p_w, p_l = site_width, site_length
    
    building_long_axis = "X" if w > h else "Y"
    site_short_axis = "X" if p_w <= p_l else "Y"
    
    aligned = is_square or (building_long_axis == site_short_axis)
    penalty = 0 if aligned else rule["penalty_rate"]
    
    return _result(
        rule["id"], f"{rule['group']}: Orientation", rule["group"],
        aligned, penalty,
        "Aligned with short edge ✓" if aligned else "Misaligned (parallel to long edge)",
        measured=f"Long axis: {building_long_axis}",
        threshold=f"Must match site short axis ({site_short_axis})",
        calc="0 pts (aligned)" if aligned else f"{rule['penalty_rate']:,} pts flat (misaligned)",
    )


# ── Dispatch and Rule List ────────────────────────────────────────────────

_EVALUATORS = {
    "center_proximity":             _eval_center_proximity,
    "center_proximity_asymmetric":  _eval_center_proximity_asymmetric,
    "boundary_setback":             _eval_boundary_setback,
    "windward_edge":                _eval_windward_edge,
    "leeward_edge":                 _eval_leeward_edge,
    "min_distance":                 _eval_min_distance,
    "max_distance":                 _eval_max_distance,
    "rack_length":                  _eval_rack_length,
    "road_proximity":               _eval_road_proximity,
    "boundary_overflow":            _eval_boundary_overflow,
    "gate_distance":                _eval_gate_distance,
    "max_gate_distance":            _eval_max_gate_distance,
    "parallel_to_short_edge":       _eval_parallel_to_short_edge,
}

RULES = [
    # Power Block
    {"id": "PB-01", "type": "center_proximity_asymmetric", "group": "Power Block", "target": "Plot Center", "penalty_rate": 100, "penalty_mode": "linear"},
    {"id": "PB-02", "type": "boundary_setback", "group": "Power Block",    "target": "Primary Road",   "threshold": 5,   "penalty_rate": 5000, "penalty_mode": "flat"},
    
    # Cooling Tower
    {"id": "CT-01", "type": "leeward_edge",     "group": "Cooling Tower",  "target": "Wind Direction", "threshold": 120, "penalty_rate": 1000, "penalty_mode": "flat"},
    {"id": "CT-02", "type": "min_distance",     "group": "Cooling Tower",  "target": "Admin Building", "threshold": 50,  "penalty_rate": 500,  "penalty_mode": "linear"},
    {"id": "CT-03", "type": "parallel_to_short_edge", "group": "Cooling Tower", "target": "Plot Short Edge", "threshold": 0, "penalty_rate": 1000, "penalty_mode": "flat"},
    {"id": "CT-04", "type": "max_distance",     "group": "Cooling Tower",  "target": "Power Block",    "threshold": 180, "penalty_rate": 100,  "penalty_mode": "linear"},
    
    # Admin Building
    {"id": "AD-01", "type": "boundary_setback", "group": "Admin Building", "target": "Primary Road",   "threshold": 20,  "penalty_rate": 1000, "penalty_mode": "flat"},
    {"id": "AD-02", "type": "max_gate_distance","group": "Admin Building", "target": "Site Gate",      "threshold": 80,  "penalty_rate": 100,  "penalty_mode": "linear"},
    {"id": "AD-03", "type": "windward_edge",    "group": "Admin Building", "target": "Wind Direction", "threshold": 30,  "penalty_rate": 1000, "penalty_mode": "flat"},
    {"id": "AD-04", "type": "max_distance",     "group": "Admin Building", "target": "Power Block",    "threshold": 150, "penalty_rate": 100,  "penalty_mode": "linear"},
    
    # Gate House
    {"id": "GH-01", "type": "boundary_setback", "group": "Gate House",     "target": "Primary Road",   "threshold": 0,   "penalty_rate": 5000, "penalty_mode": "flat"},
    {"id": "GH-02", "type": "gate_distance",    "group": "Gate House",     "target": "Site Gate",      "threshold": 10,  "penalty_rate": 200,  "penalty_mode": "linear"},
    
    # GIS
    {"id": "GIS-01", "type": "boundary_setback", "group": "GIS",           "target": "Primary Road",   "threshold": 15,  "penalty_rate": 1000, "penalty_mode": "flat"},
    
    # Flare
    {"id": "FL-01", "type": "leeward_edge",     "group": "Flare",          "target": "Wind Direction", "threshold": 30,  "penalty_rate": 1000, "penalty_mode": "flat"},
    {"id": "FL-02", "type": "min_distance",     "group": "Flare",          "target": "Admin Building", "threshold": 100, "penalty_rate": 500,  "penalty_mode": "linear"},
    {"id": "FL-03", "type": "min_distance",     "group": "Flare",          "target": "Power Block",    "threshold": 50,  "penalty_rate": 300,  "penalty_mode": "linear"},
    {"id": "FL-04", "type": "max_distance",     "group": "Flare",          "target": "Power Block",    "threshold": 150, "penalty_rate": 100,  "penalty_mode": "linear"},
    
    # WT/WWT
    {"id": "WW-01", "type": "boundary_setback", "group": "WT/WWT",         "target": "Primary Road",   "threshold": 10,  "penalty_rate": 1000, "penalty_mode": "flat"},
    {"id": "WW-02", "type": "leeward_edge",     "group": "WT/WWT",         "target": "Wind Direction", "threshold": 50,  "penalty_rate": 500,  "penalty_mode": "flat"},
    {"id": "WW-03", "type": "max_distance",     "group": "WT/WWT",         "target": "Power Block",    "threshold": 200, "penalty_rate": 100,  "penalty_mode": "linear"},
    
    # RAW Water Tank
    {"id": "WA-01", "type": "boundary_setback", "group": "RAW Water Tank", "target": "Primary Road",   "threshold": 10,  "penalty_rate": 1000, "penalty_mode": "flat"},
    {"id": "WA-02", "type": "min_distance",     "group": "RAW Water Tank", "target": "WT/WWT",         "threshold": 10,  "penalty_rate": 200,  "penalty_mode": "linear"},
    {"id": "WA-03", "type": "max_distance",     "group": "RAW Water Tank", "target": "WT/WWT",         "threshold": 80,  "penalty_rate": 100,  "penalty_mode": "linear"},
    
    # Warehouse
    {"id": "WH-01", "type": "boundary_setback", "group": "Warehouse",      "target": "Primary Road",   "threshold": 15,  "penalty_rate": 1000, "penalty_mode": "flat"},
    {"id": "WH-02", "type": "max_distance",     "group": "Warehouse",      "target": "Power Block",    "threshold": 250, "penalty_rate": 100,  "penalty_mode": "linear"},
    
    # Demi Water Tank
    {"id": "DW-02", "type": "max_distance",     "group": "Demi Water Tank","target": "RAW Water Tank", "threshold": 40,  "penalty_rate": 100,  "penalty_mode": "linear"},
    
    # Rack connections
    {"id": "PR-01", "type": "rack_length",      "group": "Power Block",    "target": "Cooling Tower",  "rack": "Pipe Rack",    "penalty_rate": 50, "penalty_mode": "linear"},
    {"id": "PR-03", "type": "rack_length",      "group": "Power Block",    "target": "WT/WWT",         "rack": "Pipe Rack",    "penalty_rate": 30, "penalty_mode": "linear"},
    {"id": "MR-02", "type": "rack_length",      "group": "Power Block",    "target": "Admin Building", "rack": "Main Rack",    "penalty_rate": 20, "penalty_mode": "linear"},
    {"id": "UR-01", "type": "rack_length",      "group": "WT/WWT",         "target": "RAW Water Tank", "rack": "Utility Rack", "penalty_rate": 40, "penalty_mode": "linear"},
    {"id": "UR-02", "type": "rack_length",      "group": "WT/WWT",         "target": "Cooling Tower",  "rack": "Utility Rack", "penalty_rate": 30, "penalty_mode": "linear"},
    {"id": "CT-03", "type": "rack_length",      "group": "GIS",            "target": "Power Block",    "rack": "Cable Tunnel", "penalty_rate": 20, "penalty_mode": "linear"},
    
    # Road clearance and boundary overflow
    {"id": "RD-01", "type": "road_proximity",   "group": "Power Block",    "threshold": 3,  "penalty_rate": 500, "penalty_mode": "linear"},
    {"id": "RD-02", "type": "road_proximity",   "group": "Cooling Tower",  "threshold": 3,  "penalty_rate": 500, "penalty_mode": "linear"},
    {"id": "RD-03", "type": "road_proximity",   "group": "Admin Building", "threshold": 3,  "penalty_rate": 500, "penalty_mode": "linear"},
]


def evaluate_all_v2(groups, racks, site_width, site_length, wind_dir, gate_point=None, plot=None):
    """
    Run all rules from the RULES data list.
    """
    by_name = {g["name"]: g for g in groups}
    results = []

    for rule in RULES:
        evaluator = _EVALUATORS.get(rule["type"])
        if evaluator is None:
            continue

        rule_type = rule["type"]

        if rule_type in ("min_distance", "max_distance", "rack_length"):
            group = by_name.get(rule["group"])
            target = by_name.get(rule["target"])
            if group is None or target is None:
                continue
            r = evaluator(rule, group, target)
        elif rule_type in ("windward_edge", "leeward_edge", "center_proximity_asymmetric"):
            group = by_name.get(rule["group"])
            if group is None:
                continue
            r = evaluator(rule, group, site_width, site_length, wind_dir=wind_dir, plot=plot)
        elif rule_type in ("road_proximity", "boundary_overflow", "boundary_setback", "center_proximity", "parallel_to_short_edge"):
            group = by_name.get(rule["group"])
            if group is None:
                continue
            r = evaluator(rule, group, site_width, site_length, plot=plot)
        elif rule_type in ("gate_distance", "max_gate_distance"):
            group = by_name.get(rule["group"])
            if group is None:
                continue
            r = evaluator(rule, group, gate_point)
        else:
            continue

        results.append(r)

    total_penalty = sum(r["penalty"] for r in results)

    all_names = [g["name"] for g in groups]
    violations_by_group = {name: [] for name in all_names}
    for r in results:
        if not r["passed"] and r["group"] in violations_by_group:
            violations_by_group[r["group"]].append(r["id"])

    return {
        "results": results,
        "total_penalty": round(total_penalty, 1),
        "violations_by_group": violations_by_group,
    }

import math

# ── Road Infrastructure Constants (Phase 05) ──────────────────────────────────
ROAD_WIDTH       = 7      # All roads are 7m wide
ROAD_SETBACK     = 5      # Perimeter road edge is 5m from site boundary
ROAD_TO_BUILDING = 3      # Min 3m from road inner edge to building
ROAD_TO_RACK     = 2      # Min 2m from road to rack
RACK_TO_BLOCK    = 2.5    # Min 2.5m from rack to building

# Inner edge of perimeter road = ROAD_SETBACK + ROAD_WIDTH = 12m from boundary
ROAD_INNER_EDGE  = ROAD_SETBACK + ROAD_WIDTH  # 12m

# Minimum building distance from boundary = road inner edge + gap
MIN_BUILDING_FROM_BOUNDARY = ROAD_INNER_EDGE + ROAD_TO_BUILDING  # 15m

# ── Helpers ────────────────────────────────────────────────────────────────

def _center(group):
    """Return (cx, cy) of a group rectangle."""
    return group["x"] + group["width"] / 2, group["y"] + group["height"] / 2


def _edge_distance(group, site_width, site_length):
    """Minimum distance from any edge of the group rect to any site boundary."""
    x, y, w, h = group["x"], group["y"], group["width"], group["height"]
    return min(x, y, site_width - (x + w), site_length - (y + h))


def _dist(cx1, cy1, cx2, cy2):
    return math.sqrt((cx1 - cx2) ** 2 + (cy1 - cy2) ** 2)


def _closest_edge(group, site_width, site_length):
    """Return (edge_name, distance) for the closest site boundary."""
    x, y, w, h = group["x"], group["y"], group["width"], group["height"]
    edges = {
        "left":   x,
        "bottom": y,
        "right":  site_width  - (x + w),
        "top":    site_length - (y + h),
    }
    name = min(edges, key=edges.get)
    return name, edges[name]


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


# ══════════════════════════════════════════════════════════════════════════
#  Phase 03 — Individual Rules (kept for backward compatibility)
# ══════════════════════════════════════════════════════════════════════════

def rule_pb01(power_block, site_width, site_length):
    """PB-01: Power Block center within 20 m of plot center = PASS.
    Beyond 20 m tolerance: 100 pts per metre of excess distance.
    """
    TOLERANCE = 20.0
    cx, cy = _center(power_block)
    site_cx, site_cy = site_width / 2, site_length / 2
    distance = _dist(cx, cy, site_cx, site_cy)
    excess  = max(0.0, distance - TOLERANCE)
    penalty = excess * 100
    passed  = excess == 0
    return _result(
        "PB-01", "Power Block: Center (±20 m)", "Power Block",
        passed, penalty,
        f"Within tolerance ✓ ({distance:.1f} m from center)" if passed else f"Off-center by {excess:.1f} m beyond 20 m tolerance",
        measured=f"{distance:.1f} m from plot center",
        threshold="≤ 20 m from center (free zone)",
        calc=f"Excess: {distance:.1f} − 20 = {excess:.1f} m × 100 pts/m = {penalty:,.0f} pts" if excess > 0 else "0 pts (within 20 m tolerance)",
    )


def rule_pb02(power_block, site_width, site_length):
    """PB-02: Power Block must not violate 5m primary road setback. 5000 pts flat."""
    setback = 5
    x, y, w, h = power_block["x"], power_block["y"], power_block["width"], power_block["height"]
    edges = {
        "left":   x,
        "bottom": y,
        "right":  site_width  - (x + w),
        "top":    site_length - (y + h),
    }
    min_edge_name = min(edges, key=edges.get)
    min_edge_val  = edges[min_edge_name]
    violated = min_edge_val < setback
    return _result(
        "PB-02", "Power Block: Road Setback", "Power Block",
        not violated,
        5000 if violated else 0,
        f"Violates 5m setback ({min_edge_name}: {min_edge_val:.1f} m)" if violated else "All edges ≥ 5m setback ✓",
        measured=f"Closest edge ({min_edge_name}): {min_edge_val:.1f} m",
        threshold="≥ 5 m on all sides",
        calc="5,000 pts flat (violation)" if violated else "0 pts (no violation)",
    )


def rule_ct01(cooling_tower, site_width, site_length, wind_dir):
    """CT-01: Cooling Tower must be on the windward edge. 1000 pts flat."""
    x, y, w, h = cooling_tower["x"], cooling_tower["y"], cooling_tower["width"], cooling_tower["height"]
    threshold = 30

    dist_map = {
        "East":  ("right edge",  site_width  - (x + w)),
        "West":  ("left edge",   x),
        "North": ("top edge",    site_length - (y + h)),
        "South": ("bottom edge", y),
    }
    edge_label, dist_to_edge = dist_map.get(wind_dir, ("right edge", site_width - (x + w)))
    on_edge = dist_to_edge <= threshold
    return _result(
        "CT-01", "Cooling Tower: Windward Edge", "Cooling Tower",
        on_edge,
        0 if on_edge else 1000,
        f"On {wind_dir} windward edge ✓" if on_edge else f"Not on {wind_dir} windward edge",
        measured=f"Distance to {edge_label}: {dist_to_edge:.1f} m",
        threshold=f"≤ {threshold} m from {edge_label} (wind = {wind_dir})",
        calc="0 pts (on edge)" if on_edge else "1,000 pts flat (not on windward edge)",
    )


def rule_ct02(cooling_tower, admin_building):
    """CT-02: Cooling Tower must be ≥ 50m from Admin Building. 500 pts/m under."""
    ct_cx, ct_cy = _center(cooling_tower)
    adm_cx, adm_cy = _center(admin_building)
    distance = _dist(ct_cx, ct_cy, adm_cx, adm_cy)
    shortfall = max(0.0, 50.0 - distance)
    penalty = shortfall * 500
    return _result(
        "CT-02", "CT ↔ Admin: Min Dist", "Cooling Tower",
        shortfall == 0,
        penalty,
        f"CT–Admin distance: {distance:.1f} m ✓" if shortfall == 0 else f"Too close: {distance:.1f} m (need ≥ 50 m)",
        measured=f"CT center → Admin center: {distance:.1f} m",
        threshold="≥ 50 m",
        calc=f"Shortfall: 50 − {distance:.1f} = {shortfall:.1f} m × 500 pts/m = {penalty:,.0f} pts" if shortfall > 0 else "0 pts (distance OK)",
    )


def rule_ad01(admin_building, site_width, site_length):
    """AD-01: Admin Building must be ≥ 20m from any site boundary. 1000 pts flat."""
    x, y, w, h = admin_building["x"], admin_building["y"], admin_building["width"], admin_building["height"]
    edges = {
        "left":   x,
        "bottom": y,
        "right":  site_width  - (x + w),
        "top":    site_length - (y + h),
    }
    min_edge_name = min(edges, key=edges.get)
    min_edge_val  = edges[min_edge_name]
    violated = min_edge_val < 20
    return _result(
        "AD-01", "Admin: Road Setback", "Admin Building",
        not violated,
        1000 if violated else 0,
        f"Too close to {min_edge_name}: {min_edge_val:.1f} m" if violated else "Admin ≥ 20m from all edges ✓",
        measured=f"Closest edge ({min_edge_name}): {min_edge_val:.1f} m",
        threshold="≥ 20 m on all sides",
        calc="1,000 pts flat (violation)" if violated else "0 pts (no violation)",
    )


def rule_ad02(admin_building, site_width):
    """AD-02: Admin Building center must be ≤ 50m from Gate House. 100 pts/m over.
    Gate House assumed at bottom-center: (site_width/2, 0).
    """
    gate_x, gate_y = site_width / 2, 0.0
    adm_cx, adm_cy = _center(admin_building)
    distance = _dist(adm_cx, adm_cy, gate_x, gate_y)
    excess = max(0.0, distance - 50.0)
    penalty = excess * 100
    return _result(
        "AD-02", "Admin: Gate Distance", "Admin Building",
        excess == 0,
        penalty,
        f"Admin–Gate: {distance:.1f} m ✓" if excess == 0 else f"Too far from gate: {distance:.1f} m (need ≤ 50 m)",
        measured=f"Admin center → Gate House: {distance:.1f} m",
        threshold="≤ 50 m",
        calc=f"Excess: {distance:.1f} − 50 = {excess:.1f} m × 100 pts/m = {penalty:,.0f} pts" if excess > 0 else "0 pts (within range)",
    )


# ── Phase 03 Master Evaluator (backward compat) ───────────────────────────

def evaluate_all(groups, site_width, site_length, wind_dir):
    """
    Run all 6 Phase 3 rules and return a structured results dict.

    Args:
        groups      : list of group dicts from Core.Groups.get_groups()
        site_width  : float — plot width in metres
        site_length : float — plot length in metres
        wind_dir    : str   — "North" | "South" | "East" | "West"

    Returns:
        {
            "results"             : list of rule result dicts,
            "total_penalty"       : float,
            "violations_by_group" : { group_name: [rule_id, ...] }
        }
    """
    by_name = {g["name"]: g for g in groups}
    pb  = by_name["Power Block"]
    ct  = by_name["Cooling Tower"]
    adm = by_name["Admin Building"]

    results = [
        rule_pb01(pb,  site_width, site_length),
        rule_pb02(pb,  site_width, site_length),
        rule_ct01(ct,  site_width, site_length, wind_dir),
        rule_ct02(ct,  adm),
        rule_ad01(adm, site_width, site_length),
        rule_ad02(adm, site_width),
    ]

    total_penalty = sum(r["penalty"] for r in results)

    violations_by_group = {g["name"]: [] for g in groups}
    for r in results:
        if not r["passed"]:
            violations_by_group[r["group"]].append(r["id"])

    return {
        "results": results,
        "total_penalty": round(total_penalty, 1),
        "violations_by_group": violations_by_group,
    }


# ══════════════════════════════════════════════════════════════════════════
#  Phase 04 — Generic Rule Engine (data-driven by RULES list)
# ══════════════════════════════════════════════════════════════════════════

# ── RULES data list — mirrors !Scoring_Logic.md ───────────────────────────
# Each dict maps 1:1 to a row in the Scoring Logic table.
# "type" must match one of the generic evaluator keys in _EVALUATORS.

RULES = [
    # ── Phase 03 rules (re-declared as data) ──────────────────────────────
    {"id": "PB-01", "type": "center_proximity", "group": "Power Block",    "target": "Plot Center",    "threshold": 20,  "penalty_rate": 100,  "penalty_mode": "linear"},
    {"id": "PB-02", "type": "boundary_setback", "group": "Power Block",    "target": "Primary Road",   "threshold": 5,   "penalty_rate": 5000, "penalty_mode": "flat"},
    {"id": "CT-01", "type": "leeward_edge",     "group": "Cooling Tower",  "target": "Wind Direction", "threshold": 30,  "penalty_rate": 1000, "penalty_mode": "flat"},
    {"id": "CT-02", "type": "min_distance",     "group": "Cooling Tower",  "target": "Admin Building", "threshold": 50,  "penalty_rate": 500,  "penalty_mode": "linear"},
    {"id": "AD-01", "type": "boundary_setback", "group": "Admin Building", "target": "Primary Road",   "threshold": 20,  "penalty_rate": 1000, "penalty_mode": "flat"},
    {"id": "AD-02", "type": "max_distance",     "group": "Admin Building", "target": "Gate House",     "threshold": 50,  "penalty_rate": 100,  "penalty_mode": "linear"},
    {"id": "AD-03", "type": "windward_edge",    "group": "Admin Building", "target": "Wind Direction", "threshold": 30,  "penalty_rate": 1000, "penalty_mode": "flat"},

    # ── Phase 04 new rules ────────────────────────────────────────────────
    # Gate House
    {"id": "GH-01", "type": "boundary_setback", "group": "Gate House",     "target": "Primary Road",   "threshold": 0,   "penalty_rate": 5000, "penalty_mode": "flat"},



    # LPG/Metering
    {"id": "LP-01", "type": "boundary_setback", "group": "LPG/Metering",   "target": "Primary Road",   "threshold": 10,  "penalty_rate": 1000, "penalty_mode": "flat"},
    {"id": "LP-02", "type": "min_distance",     "group": "LPG/Metering",   "target": "Power Block",    "threshold": 30,  "penalty_rate": 300,  "penalty_mode": "linear"},

    # Flare
    {"id": "FL-01", "type": "leeward_edge",     "group": "Flare",          "target": "Wind Direction", "threshold": 30,  "penalty_rate": 1000, "penalty_mode": "flat"},
    {"id": "FL-02", "type": "min_distance",     "group": "Flare",          "target": "Admin Building", "threshold": 100, "penalty_rate": 500,  "penalty_mode": "linear"},
    {"id": "FL-03", "type": "min_distance",     "group": "Flare",          "target": "Power Block",    "threshold": 50,  "penalty_rate": 300,  "penalty_mode": "linear"},

    # WT/WWT
    {"id": "WW-01", "type": "boundary_setback", "group": "WT/WWT",         "target": "Primary Road",   "threshold": 10,  "penalty_rate": 1000, "penalty_mode": "flat"},
    {"id": "WW-02", "type": "leeward_edge",     "group": "WT/WWT",         "target": "Wind Direction", "threshold": 50,  "penalty_rate": 500,  "penalty_mode": "flat"},

    # Water
    {"id": "WA-01", "type": "boundary_setback", "group": "Water",          "target": "Primary Road",   "threshold": 10,  "penalty_rate": 1000, "penalty_mode": "flat"},
    {"id": "WA-02", "type": "min_distance",     "group": "Water",          "target": "WT/WWT",         "threshold": 10,  "penalty_rate": 200,  "penalty_mode": "linear"},
    {"id": "WA-03", "type": "max_distance",     "group": "Water",          "target": "WT/WWT",         "threshold": 80,  "penalty_rate": 100,  "penalty_mode": "linear"},

    # Rack length rules — shorter connection = lower penalty
    # Pipe Rack connections
    {"id": "PR-01", "type": "rack_length", "group": "Power Block",   "target": "Cooling Tower",  "rack": "Pipe Rack",    "penalty_rate": 50, "penalty_mode": "linear"},
    {"id": "PR-02", "type": "rack_length", "group": "Power Block",   "target": "LPG/Metering",   "rack": "Pipe Rack",    "penalty_rate": 30, "penalty_mode": "linear"},
    {"id": "PR-03", "type": "rack_length", "group": "Power Block",   "target": "WT/WWT",         "rack": "Pipe Rack",    "penalty_rate": 30, "penalty_mode": "linear"},
    # Main Rack connections
    {"id": "MR-02", "type": "rack_length", "group": "Power Block",   "target": "Admin Building", "rack": "Main Rack",    "penalty_rate": 20, "penalty_mode": "linear"},
    # Utility Rack connections
    {"id": "UR-01", "type": "rack_length", "group": "WT/WWT",        "target": "Water",          "rack": "Utility Rack", "penalty_rate": 40, "penalty_mode": "linear"},
    {"id": "UR-02", "type": "rack_length", "group": "WT/WWT",        "target": "Cooling Tower",  "rack": "Utility Rack", "penalty_rate": 30, "penalty_mode": "linear"},
    # Cable Tunnel connection (GIS ↔ Power Block)
    {"id": "CT-03", "type": "rack_length", "group": "GIS",           "target": "Power Block",    "rack": "Cable Tunnel", "penalty_rate": 20, "penalty_mode": "linear"},

    # ── Phase 05 new rules ────────────────────────────────────────────
    # GIS
    {"id": "GIS-01", "type": "boundary_setback", "group": "GIS",       "target": "Primary Road",   "threshold": 15,  "penalty_rate": 1000, "penalty_mode": "flat"},
    # Warehouse
    {"id": "WH-01", "type": "boundary_setback", "group": "Warehouse",  "target": "Primary Road",   "threshold": 15,  "penalty_rate": 1000, "penalty_mode": "flat"},
    # Road proximity rules (building must be >= 3m from road inner edge = >= 15m from boundary)
    {"id": "RD-01", "type": "road_proximity", "group": "Power Block",    "threshold": 3,  "penalty_rate": 500, "penalty_mode": "linear"},
    {"id": "RD-02", "type": "road_proximity", "group": "Cooling Tower",  "threshold": 3,  "penalty_rate": 500, "penalty_mode": "linear"},
    {"id": "RD-03", "type": "road_proximity", "group": "Admin Building", "threshold": 3,  "penalty_rate": 500, "penalty_mode": "linear"},
]


# ── Generic evaluator functions ───────────────────────────────────────────

def _eval_center_proximity(rule, group, site_width, site_length, **_):
    """Distance from building center to plot center. Linear penalty on excess."""
    cx, cy = _center(group)
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


def _eval_boundary_setback(rule, group, site_width, site_length, **_):
    """Min distance from any group edge to site boundary. Flat penalty."""
    edge_name, edge_val = _closest_edge(group, site_width, site_length)
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


def _eval_windward_edge(rule, group, site_width, site_length, wind_dir, **_):
    """Check if building is on the windward edge. Flat penalty."""
    x, y, w, h = group["x"], group["y"], group["width"], group["height"]
    dist_map = {
        "East":  ("right edge",  site_width  - (x + w)),
        "West":  ("left edge",   x),
        "North": ("top edge",    site_length - (y + h)),
        "South": ("bottom edge", y),
    }
    edge_label, dist_to_edge = dist_map.get(wind_dir, ("right edge", site_width - (x + w)))
    on_edge = dist_to_edge <= rule["threshold"]
    penalty = 0 if on_edge else rule["penalty_rate"]
    return _result(
        rule["id"], f"{rule['group']}: Windward Edge", rule["group"],
        on_edge, penalty,
        f"On {wind_dir} windward edge ✓" if on_edge else f"Not on {wind_dir} windward edge",
        measured=f"Distance to {edge_label}: {dist_to_edge:.1f} m",
        threshold=f"≤ {rule['threshold']} m from {edge_label} (wind = {wind_dir})",
        calc="0 pts (on edge)" if on_edge else f"{rule['penalty_rate']:,} pts flat (not on windward edge)",
    )


def _eval_leeward_edge(rule, group, site_width, site_length, wind_dir, **_):
    """Check if building is on the leeward (downwind) edge. Flat penalty.
    Leeward = OPPOSITE side of wind direction.
    """
    x, y, w, h = group["x"], group["y"], group["width"], group["height"]
    # Leeward is opposite of wind: if wind is East, leeward side is left (West)
    dist_map = {
        "East":  ("left edge (downwind)",   x),
        "West":  ("right edge (downwind)",  site_width  - (x + w)),
        "North": ("bottom edge (downwind)", y),
        "South": ("top edge (downwind)",    site_length - (y + h)),
    }
    edge_label, dist_to_edge = dist_map.get(wind_dir, ("left edge (downwind)", x))
    on_edge = dist_to_edge <= rule["threshold"]
    penalty = 0 if on_edge else rule["penalty_rate"]
    return _result(
        rule["id"], f"{rule['group']}: Leeward Edge (Downwind)", rule["group"],
        on_edge, penalty,
        f"On downwind ({wind_dir} leeward) edge" if on_edge else f"Not on downwind edge",
        measured=f"Distance to {edge_label}: {dist_to_edge:.1f} m",
        threshold=f"<= {rule['threshold']} m from {edge_label} (wind = {wind_dir})",
        calc="0 pts (on edge)" if on_edge else f"{rule['penalty_rate']:,} pts flat (not on downwind edge)",
    )


def _eval_min_distance(rule, group, target_group, **_):
    """Center-to-center distance must be ≥ threshold. Linear penalty on shortfall."""
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
    """Center-to-center distance must be ≤ threshold. Linear penalty on excess."""
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


def _eval_pipe_rack_proximity(rule, rack, target_group, **_):
    """Distance from rack line to target building center. Linear penalty on excess."""
    cx, cy = _center(target_group)
    x1, y1 = rack["start"]
    x2, y2 = rack["end"]
    distance = _point_to_line_dist(cx, cy, x1, y1, x2, y2)
    excess = max(0.0, distance - rule["threshold"])
    penalty = excess * rule["penalty_rate"]
    return _result(
        rule["id"], f"{rule['group']} ↔ {rule['target']}: Rack Proximity", rule["group"],
        excess == 0, penalty,
        f"Rack within {distance:.1f} m ✓" if excess == 0 else f"Rack too far: {distance:.1f} m (need ≤ {rule['threshold']} m)",
        measured=f"{distance:.1f} m from rack to building center",
        threshold=f"≤ {rule['threshold']} m",
        calc=f"Excess: {distance:.1f} − {rule['threshold']} = {excess:.1f} m × {rule['penalty_rate']} pts/m = {penalty:,.0f} pts" if excess > 0 else "0 pts (OK)",
    )


def _eval_rack_length(rule, group, target_group, **_):
    """Edge-to-edge distance between two connected buildings (rack length).
    Penalty = distance × penalty_rate. No threshold — shorter is always better.
    """
    distance = _rect_edge_distance(group, target_group)
    penalty = distance * rule["penalty_rate"]
    rack_name = rule.get("rack", "Rack")
    return _result(
        rule["id"],
        f"{rack_name}: {rule['group']} \u2194 {rule['target']}",
        rack_name,  # attribute penalty to the rack, not a building
        distance == 0, penalty,
        f"Edge-to-edge: {distance:.1f} m" if distance > 0 else "Adjacent (0 m)",
        measured=f"{distance:.1f} m edge-to-edge",
        threshold="0 m (as short as possible)",
        calc=f"{distance:.1f} m \u00d7 {rule['penalty_rate']} pts/m = {penalty:,.0f} pts" if distance > 0 else "0 pts (adjacent)",
    )


def _eval_road_proximity(rule, group, site_width, site_length, **_):
    """Distance from building edge to nearest perimeter road inner edge.
    Road inner edge = ROAD_SETBACK + ROAD_WIDTH = 12m from boundary.
    Building must be >= threshold (3m) from road inner edge.
    Linear penalty on shortfall.
    """
    x, y, w, h = group["x"], group["y"], group["width"], group["height"]
    road_inner = ROAD_INNER_EDGE  # 12m from boundary

    # Distance from each building edge to the nearest road inner edge
    dist_left   = x - road_inner
    dist_bottom = y - road_inner
    dist_right  = (site_width - (x + w)) - road_inner
    dist_top    = (site_length - (y + h)) - road_inner

    min_dist = min(dist_left, dist_bottom, dist_right, dist_top)
    edges = {"left": dist_left, "bottom": dist_bottom, "right": dist_right, "top": dist_top}
    closest_edge = min(edges, key=edges.get)

    shortfall = max(0.0, rule["threshold"] - min_dist)
    penalty = shortfall * rule["penalty_rate"]
    passed = shortfall == 0
    return _result(
        rule["id"], f"{rule['group']}: Road Gap", rule["group"],
        passed, penalty,
        f"Road gap OK ({min_dist:.1f} m from {closest_edge} road) \u2713" if passed else f"Too close to {closest_edge} road: {min_dist:.1f} m (need \u2265 {rule['threshold']} m)",
        measured=f"Closest road edge ({closest_edge}): {min_dist:.1f} m",
        threshold=f"\u2265 {rule['threshold']} m from road inner edge",
        calc=f"Shortfall: {rule['threshold']} \u2212 {min_dist:.1f} = {shortfall:.1f} m \u00d7 {rule['penalty_rate']} pts/m = {penalty:,.0f} pts" if shortfall > 0 else "0 pts (OK)",
    )


def _eval_boundary_overflow(rule, group, site_width, site_length, **_):
    """Check if building extends past site boundary.
    Logarithmic penalty to discourage but not hard-reject overflow.
    """
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
        f"Within boundaries \u2713" if passed else f"Overflows boundary by {total_overflow:.1f} m total",
        measured=f"Total overflow: {total_overflow:.1f} m",
        threshold="0 m (should stay within boundary)",
        calc=f"{rule['penalty_rate']} \u00d7 ln(1 + {total_overflow:.1f}) = {penalty:,.0f} pts" if total_overflow > 0 else "0 pts (OK)",
    )


# ── Evaluator dispatch table ──────────────────────────────────────────────

_EVALUATORS = {
    "center_proximity":    _eval_center_proximity,
    "boundary_setback":    _eval_boundary_setback,
    "windward_edge":       _eval_windward_edge,
    "leeward_edge":        _eval_leeward_edge,
    "min_distance":        _eval_min_distance,
    "max_distance":        _eval_max_distance,
    "pipe_rack_proximity": _eval_pipe_rack_proximity,
    "rack_length":         _eval_rack_length,
    "road_proximity":      _eval_road_proximity,
    "boundary_overflow":   _eval_boundary_overflow,
}


# ── Phase 04 Master Evaluator ─────────────────────────────────────────────

def evaluate_all_v2(groups, racks, site_width, site_length, wind_dir):
    """
    Run all rules from the RULES data list using generic evaluators.

    Args:
        groups      : list of group dicts (rectangles)
        racks       : list of rack dicts (polylines)
        site_width  : float — plot width in metres
        site_length : float — plot length in metres
        wind_dir    : str   — "North" | "South" | "East" | "West"

    Returns:
        {
            "results"             : list of rule result dicts,
            "total_penalty"       : float,
            "violations_by_group" : { group_name: [rule_id, ...] }
        }
    """
    by_name = {g["name"]: g for g in groups}
    rack_by_name = {r["name"]: r for r in racks}

    results = []

    for rule in RULES:
        evaluator = _EVALUATORS.get(rule["type"])
        if evaluator is None:
            continue  # unknown rule type — skip silently

        rule_type = rule["type"]

        # Resolve the primary group/rack
        if rule_type == "pipe_rack_proximity":
            # For rack rules: group = the rack, target = the building
            rack = rack_by_name.get(rule["group"])
            target = by_name.get(rule["target"])
            if rack is None or target is None:
                continue
            r = evaluator(rule, rack, target)
        elif rule_type in ("min_distance", "max_distance"):
            # Two-building rules
            group = by_name.get(rule["group"])
            target = by_name.get(rule["target"])
            if group is None or target is None:
                continue
            r = evaluator(rule, group, target)
        elif rule_type == "rack_length":
            # Two-building rack connection rule
            group = by_name.get(rule["group"])
            target = by_name.get(rule["target"])
            if group is None or target is None:
                continue
            r = evaluator(rule, group, target)
        elif rule_type in ("windward_edge", "leeward_edge"):
            group = by_name.get(rule["group"])
            if group is None:
                continue
            r = evaluator(rule, group, site_width, site_length, wind_dir)
        elif rule_type in ("road_proximity", "boundary_overflow"):
            # Road/boundary rules — same signature as boundary_setback
            group = by_name.get(rule["group"])
            if group is None:
                continue
            r = evaluator(rule, group, site_width, site_length)
        else:
            # Single-building rules (center_proximity, boundary_setback)
            group = by_name.get(rule["group"])
            if group is None:
                continue
            r = evaluator(rule, group, site_width, site_length)

        results.append(r)

    total_penalty = sum(r["penalty"] for r in results)

    # Build violations map for all groups + racks
    all_names = [g["name"] for g in groups] + [r["name"] for r in racks]
    violations_by_group = {name: [] for name in all_names}
    for r in results:
        if not r["passed"] and r["group"] in violations_by_group:
            violations_by_group[r["group"]].append(r["id"])

    return {
        "results": results,
        "total_penalty": round(total_penalty, 1),
        "violations_by_group": violations_by_group,
    }

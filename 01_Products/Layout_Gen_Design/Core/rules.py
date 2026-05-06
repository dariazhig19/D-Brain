import math

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


# ── Individual Rules ────────────────────────────────────────────────────────

def rule_pb01(power_block, site_width, site_length):
    """PB-01: Power Block center must be close to the plot center. 100 pts/m."""
    cx, cy = _center(power_block)
    site_cx, site_cy = site_width / 2, site_length / 2
    distance = _dist(cx, cy, site_cx, site_cy)
    penalty = distance * 100
    passed = distance < 1.0
    return _result(
        "PB-01", "Power Block: Center", "Power Block",
        passed, penalty,
        "Within 1m of center ✓" if passed else f"Power Block is off-center",
        measured=f"{distance:.1f} m from center",
        threshold="< 1 m (perfect) or 0 pts/m penalty",
        calc=f"{distance:.1f} m × 100 pts/m = {penalty:,.0f} pts",
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


# ── Master Evaluator ────────────────────────────────────────────────────────

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

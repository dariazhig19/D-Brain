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


# ── Individual Rules ────────────────────────────────────────────────────────

def rule_pb01(power_block, site_width, site_length):
    """PB-01: Power Block center must be close to the plot center. 100 pts/m."""
    cx, cy = _center(power_block)
    site_cx, site_cy = site_width / 2, site_length / 2
    distance = _dist(cx, cy, site_cx, site_cy)
    penalty = distance * 100
    return {
        "id": "PB-01",
        "name": "Power Block: Center",
        "group": "Power Block",
        "passed": distance < 1.0,   # within 1m = perfect
        "penalty": round(penalty, 1),
        "message": f"Distance from center: {distance:.1f} m",
    }


def rule_pb02(power_block, site_width, site_length):
    """PB-02: Power Block must not violate 5m primary road setback. 5000 pts flat."""
    setback = 5
    x, y, w, h = power_block["x"], power_block["y"], power_block["width"], power_block["height"]
    violated = (
        x < setback or
        y < setback or
        (x + w) > (site_width - setback) or
        (y + h) > (site_length - setback)
    )
    return {
        "id": "PB-02",
        "name": "Power Block: Road Setback",
        "group": "Power Block",
        "passed": not violated,
        "penalty": 5000 if violated else 0,
        "message": "Violates 5m primary road setback" if violated else "Setback OK",
    }


def rule_ct01(cooling_tower, site_width, site_length, wind_dir):
    """CT-01: Cooling Tower must be on the windward edge. 1000 pts flat.
    Windward = the side FROM WHICH the wind blows.
    threshold = 30m from the respective edge counts as 'on edge'.
    """
    x, y, w, h = cooling_tower["x"], cooling_tower["y"], cooling_tower["width"], cooling_tower["height"]
    threshold = 30

    windward_checks = {
        "East":  (x + w) >= (site_width - threshold),    # right side
        "West":  x <= threshold,                          # left side
        "North": (y + h) >= (site_length - threshold),   # top side
        "South": y <= threshold,                          # bottom side
    }
    on_edge = windward_checks.get(wind_dir, True)
    return {
        "id": "CT-01",
        "name": "Cooling Tower: Windward Edge",
        "group": "Cooling Tower",
        "passed": on_edge,
        "penalty": 0 if on_edge else 1000,
        "message": f"On {wind_dir} windward edge ✓" if on_edge else f"Not on {wind_dir} windward edge",
    }


def rule_ct02(cooling_tower, admin_building):
    """CT-02: Cooling Tower must be ≥ 50m from Admin Building. 500 pts/m under."""
    ct_cx, ct_cy = _center(cooling_tower)
    adm_cx, adm_cy = _center(admin_building)
    distance = _dist(ct_cx, ct_cy, adm_cx, adm_cy)
    shortfall = max(0.0, 50.0 - distance)
    penalty = shortfall * 500
    return {
        "id": "CT-02",
        "name": "CT ↔ Admin: Min Dist (50m)",
        "group": "Cooling Tower",
        "passed": shortfall == 0,
        "penalty": round(penalty, 1),
        "message": f"CT–Admin distance: {distance:.1f} m (need ≥ 50 m)",
    }


def rule_ad01(admin_building, site_width, site_length):
    """AD-01: Admin Building must be ≥ 20m from any site boundary. 1000 pts flat."""
    min_edge = _edge_distance(admin_building, site_width, site_length)
    violated = min_edge < 20
    return {
        "id": "AD-01",
        "name": "Admin: Road Setback (20m)",
        "group": "Admin Building",
        "passed": not violated,
        "penalty": 1000 if violated else 0,
        "message": f"Min edge distance: {min_edge:.1f} m (need ≥ 20 m)",
    }


def rule_ad02(admin_building, site_width):
    """AD-02: Admin Building center must be ≤ 50m from Gate House. 100 pts/m over.
    Gate House assumed at bottom-center: (site_width/2, 0).
    """
    gate_x, gate_y = site_width / 2, 0.0
    adm_cx, adm_cy = _center(admin_building)
    distance = _dist(adm_cx, adm_cy, gate_x, gate_y)
    excess = max(0.0, distance - 50.0)
    penalty = excess * 100
    return {
        "id": "AD-02",
        "name": "Admin: Gate Distance (≤50m)",
        "group": "Admin Building",
        "passed": excess == 0,
        "penalty": round(penalty, 1),
        "message": f"Admin–Gate distance: {distance:.1f} m (need ≤ 50 m)",
    }


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

    # Build per-group violation lookup for the dashboard overlay
    violations_by_group = {g["name"]: [] for g in groups}
    for r in results:
        if not r["passed"]:
            violations_by_group[r["group"]].append(r["id"])

    return {
        "results": results,
        "total_penalty": round(total_penalty, 1),
        "violations_by_group": violations_by_group,
    }

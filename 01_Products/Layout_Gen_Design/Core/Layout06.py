"""Phase 06 — Steps 1.1–1.3: Grid-first block placement + fire road sketches.

Steps covered:
  1.1  2m grid setup, all blocks snap to grid
  1.2  Placement sequence + fire road geometry
  1.3  Block buffer: 8m between block edges
"""

import random

# ── Constants ──────────────────────────────────────────────────────────────
CELL_SIZE         = 2    # metres per grid cell
BLOCK_BUFFER      = 8    # min gap between block edges
PB_RING_OFFSET    = 8    # ring centerline from PB face (4m setback + 4m half-road)
PERIMETER_SETBACK = 5    # perimeter road outer edge from plot boundary ← configurable
PERIMETER_ROAD_W  = 8    # perimeter road width
PERIMETER_CL_DIST = PERIMETER_SETBACK + PERIMETER_ROAD_W / 2   # 9m from boundary

# ── Block catalog ──────────────────────────────────────────────────────────
# (width, height) — non-square blocks may be rotated 90° during placement
BLOCK_FOOTPRINTS = {
    "Power Block":    (150, 150),
    "Cooling Tower":  (40,  183),
    "Admin Building": (30,   25),
    "Gate House":     (12,   12),
    "GIS":            (110,  51),
    "Warehouse":      (59,   40),
    "Flare":          (40,   40),
    "WT/WWT":         (81,   56),
    "RAW Water Tank": (37,   37),
    "Demi Water Tank":(25,   12),
    "EDG":            (20,   15),
    "Fire Water":     (15,   12),
}

BLOCK_COLORS = {
    "Power Block":    "#4a90d9",
    "Cooling Tower":  "#7ed6a0",
    "Admin Building": "#f5a623",
    "Gate House":     "#9b59b6",
    "GIS":            "#2c3e50",
    "Warehouse":      "#e67e22",
    "Flare":          "#e74c3c",
    "WT/WWT":         "#34495e",
    "RAW Water Tank": "#00bcd4",
    "Demi Water Tank":"#1abc9c",
    "EDG":            "#8e44ad",
    "Fire Water":     "#c0392b",
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

def _overlaps_any(placed, x, y, w, h, gap=BLOCK_BUFFER):
    """placed: dict of name → (x, y, w, h)"""
    for bx, by, bw, bh in placed.values():
        if _overlaps(x, y, w, h, bx, by, bw, bh, gap):
            return True
    return False

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


def _try_place(sw, sl, name, placed, sample_fn, max_attempts=500):
    """
    Try to place block using sample_fn() → (x, y).
    Tries BOTH orientations (w×h and h×w) at each sampled point.
    Returns (x, y, w, h) or None.
    """
    base_w, base_h = BLOCK_FOOTPRINTS[name]
    orientations = [(base_w, base_h)]
    if base_w != base_h:                      # non-square → also try rotated
        orientations.append((base_h, base_w))

    valid = []
    for _ in range(max_attempts):
        rx, ry = sample_fn()
        for w, h in orientations:
            x, y = snap_xy(rx, ry)
            x = max(0, min(x, sw - w))
            y = max(0, min(y, sl - h))
            if not _overlaps_any(placed, x, y, w, h):
                valid.append((x, y, w, h))

    return random.choice(valid) if valid else None


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

# ── Sample functions for floated blocks ───────────────────────────────────
def _leeward(sw, sl, wind_dir, name):
    """Leeward-zone sampler. Returns a lambda → (x, y)."""
    base_w, base_h = BLOCK_FOOTPRINTS[name]
    # Use the smaller dimension for zone calculation (block may rotate)
    small = min(base_w, base_h)
    large = max(base_w, base_h)
    b = BLOCK_BUFFER
    if wind_dir == "East":
        return lambda: (random.uniform(b, sw * 0.45),
                        random.uniform(b, sl - small - b))
    elif wind_dir == "West":
        return lambda: (random.uniform(sw * 0.55, sw - small - b),
                        random.uniform(b, sl - small - b))
    elif wind_dir == "North":
        return lambda: (random.uniform(b, sw - small - b),
                        random.uniform(b, sl * 0.45))
    else:  # South
        return lambda: (random.uniform(b, sw - small - b),
                        random.uniform(sl * 0.55, sl - small - b))

def _near(sw, sl, name, ref_x, ref_y, spread=80):
    b = BLOCK_BUFFER
    small = min(BLOCK_FOOTPRINTS[name])
    return lambda: (
        max(b, min(ref_x + random.uniform(-spread, spread), sw - small - b)),
        max(b, min(ref_y + random.uniform(-spread, spread), sl - small - b)),
    )

def _anywhere(sw, sl, name):
    b = BLOCK_BUFFER
    small = min(BLOCK_FOOTPRINTS[name])
    return lambda: (random.uniform(b, sw - small - b),
                    random.uniform(b, sl - small - b))

# ── Gate point ─────────────────────────────────────────────────────────────
def compute_gate(sw, sl, side, ratio):
    if side == "N": return (sw * ratio, sl)
    if side == "S": return (sw * ratio, 0)
    if side == "E": return (sw, sl * ratio)
    return (0, sl * ratio)

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
      4. Floated blocks (CT, WT/WWT, Warehouse, Flare, Admin, Demi, EDG, Fire Water)
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
        pw, ph = BLOCK_FOOTPRINTS["Power Block"]
        pb_result = _try_place(sw, sl, "Power Block", placed,
                               lambda: (
                                   (sw-pw)/2 + random.uniform(-sw*0.05, sw*0.05),
                                   (sl-ph)/2 + random.uniform(-sl*0.05, sl*0.05),
                               ), max_attempts=100)
        if pb_result is None:
            continue
        pb_x, pb_y, pb_w, pb_h = pb_result
        placed["Power Block"] = pb_result
        pb_cx, pb_cy = pb_x + pb_w/2, pb_y + pb_h/2

        # 3. PB Ring Road (geometry only — no block in placed)
        ring_road = build_pb_ring_road(pb_x, pb_y, pb_w, pb_h)

        # 4. Floated blocks
        raw_x, raw_y = placed["RAW Water Tank"][:2]
        gh_x, gh_y   = placed["Gate House"][:2]

        floated = [
            ("Cooling Tower",   _leeward(sw, sl, wind_dir, "Cooling Tower")),
            ("WT/WWT",          _near(sw, sl, "WT/WWT",        raw_x, raw_y)),
            ("Warehouse",       _anywhere(sw, sl, "Warehouse")),
            ("Flare",           _leeward(sw, sl, wind_dir, "Flare")),
            ("Admin Building",  _near(sw, sl, "Admin Building",
                                      (gh_x + pb_cx)/2, (gh_y + pb_cy)/2, spread=60)),
            ("Demi Water Tank", _near(sw, sl, "Demi Water Tank", raw_x, raw_y)),
            ("EDG",             _near(sw, sl, "EDG",            pb_cx, pb_cy, spread=60)),
            ("Fire Water",      _anywhere(sw, sl, "Fire Water")),
        ]

        ok = True
        for name, fn in floated:
            pos = _try_place(sw, sl, name, placed, fn)
            if pos is None:
                ok = False
                break
            placed[name] = pos   # (x, y, w, h) with actual (possibly rotated) dims
        if not ok:
            continue

        # 5. Perimeter Fire Road (geometry only)
        perimeter_road = build_perimeter_road(sw, sl)

        # Build output
        blocks = [
            {"name": n, "x": x, "y": y, "width": w, "height": h,
             "color": BLOCK_COLORS.get(n, "#aaaaaa"),
             "rotated": (w, h) != BLOCK_FOOTPRINTS.get(n, (w, h))}
            for n, (x, y, w, h) in placed.items()
        ]

        return {
            "blocks":         blocks,
            "ring_road":      ring_road,
            "perimeter_road": perimeter_road,
            "gate_point":     gate_pt,
            "pb_center":      (pb_cx, pb_cy),
            "cell_size":      CELL_SIZE,
            "block_buffer":   BLOCK_BUFFER,
            "pb_ring_offset": PB_RING_OFFSET,
            "perimeter_cl":   PERIMETER_CL_DIST,
        }

    return None

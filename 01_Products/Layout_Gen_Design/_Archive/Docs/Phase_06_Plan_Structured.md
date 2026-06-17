# Phase 06: Grid-First Generative Layout — Structured Reference

**Replaces:** Phase 05 (continuous float coordinates + entrance-based A* routing)
**Status:** UI transitioning to the 4-step interactive wizard (Generate & Refine modes).

---

## §0. Core Concept

Four-step interactive generative system (Generate & Refine modes).

- **Step 1 (Generate Mode)**: Automatically generates 100+ layout alternatives focusing on core large blocks. User selects the top 3 favorites to refine.
- **Step 2 (Refine Mode - Detailing)**: Places remaining small blocks based on the 3 selected layouts and subdivides large blocks into detailed individual buildings. User selects the top 3 detailed layouts.
- **Step 3 (Refine Mode - Variation)**: Generates slightly mutated, similar variations of the selected layouts from Step 2 without adding new elements. User finalizes the top 1~3 layouts.
- **Step 4 (Final Export)**: Verifies all constraints and outputs the final 1~3 layouts as CAD drawings (DXF).

**Principle:** Roads come *before* buildings. Blocks are placed around roads, not the other way around. Racks are more important than roads — placed before perimeter/spurs/stubs so roads route around rack corridors.

---

## §1. Block Catalog

| #  | Block Name       | Contents                                                                        | Notes                     |
|----|------------------|---------------------------------------------------------------------------------|---------------------------|
| 1  | Power Block      | GT Bldg, ST Bldg, HRSG, Control Bldg, Main Stack, Transformers                 | Central anchor — first    |
| 2  | GIS              | 345kV GIS, GIS Control Bldg                                                     | Near NE boundary          |
| 3  | Cooling Tower    | Cooling Tower, CW Pump, CT Electrical                                           | Leeward zone              |
| 4  | Flare            | Flare Stack, Flare KO Drum, N₂ for Flare                                       | Leeward corner            |
| 5  | WT/WWT           | WT/WWT Bldg, Chemical Storage, Clarifiers, WT/WWT Pump Room                    | Downwind                  |
| 6  | RAW Water Tank   | RAW Water Tank, Buffer Pond, Supply Pump                                        | Near water tie-in         |
| 7  | Demi Water Tank  | Demi Water Tank, Potable Water Tank                                             | Near RAW Water            |
| 8  | Admin Building   | Admin Bldg, Parking                                                             | Near Gate                 |
| 9  | Gate House       | Gate House                                                                      | Fixed on boundary         |
| 10 | Warehouse        | Machine Shop & Warehouse, AUX/LPG Boiler, Oil Storage                          | Near boundary road        |

**Footprints (w × h metres):**

| Block            | Width | Height |
|------------------|-------|--------|
| Power Block      | 150   | 150    |
| Cooling Tower    | 40    | 183    |
| Admin Building   | 30    | 25     |
| Gate House       | 12    | 12     |
| GIS              | 110   | 51     |
| Flare            | 40    | 40     |
| WT/WWT           | 81    | 56     |
| Warehouse        | 59    | 40     |
| RAW Water Tank   | 37    | 37     |
| Demi Water Tank  | 25    | 12     |

Non-square blocks may be rotated 90°.

---

## §2. Grid & Coordinate System

| Constant             | Value    | Meaning                                      |
|----------------------|----------|----------------------------------------------|
| `CELL_SIZE`          | 2 m      | Metres per grid cell                         |
| `ROAD_BUFFER`        | 8 m      | Min distance from block edge to road CL      |
| `BLOCK_BUFFER`       | 16 m     | Min gap between two block edges (no rack)    |
| `BOUNDARY_MARGIN`    | 17 m     | Min distance from floated block to boundary  |
| `BOUNDARY_TOLERANCE` | 10 m     | Leeway for tight border fits                 |
| `PB_RING_OFFSET`     | 14 m     | PB ring road CL from PB face                 |
| `PERIMETER_SETBACK`  | 5 m      | Perimeter road outer edge from plot boundary |
| `PERIMETER_ROAD_W`   | 8 m      | Perimeter road width                         |
| `PERIMETER_CL_DIST`  | 9 m      | Perimeter road CL from boundary (5 + 8/2)   |

All block positions snap to the 2m grid (`snap(v) = round(v / 2) * 2`).

---

## §3. Step 1 — Block + Road + Rack Sketch

### §3.1 Master Placement Sequence

```
1.  Fixed anchors        →  Gate House, GIS, RAW Water Tank
2.  Power Block          →  Site center ± jitter
3.  PB Ring Road         →  Geometry drawn; corridor locked for floated-block placement
4.  Gate Spur + Ring Spur→  Both spurs built from fixed anchors before floated blocks
5.  Boom Barrier         →  16m line from Gate House inner edge
6.  Floated blocks       →  Cooling Tower, WT/WWT, Warehouse, Flare, Admin, Demi Water
7.  Pipe Rack            →  6m rack network (§3.6) — before perimeter/spurs/stubs
8.  Block road buffers   →  Snapped buffer rectangles computed (§3.7.A)
9.  Perimeter Fire Road  →  Segment generation from buffers (§3.7.B)
10. Group A access roads →  8m connection lines per block (§3.8.B)
11. Segment cleanup      →  Parallel merge pass (§3.7.C)
```

---

### §3.2 Fixed Anchor Placement

Fixed anchors use `place_anchor(sw, sl, name, edge, ratio, offset)` — result is grid-snapped and clamped to plot bounds.

| # | Block          | Position Rule                         | Buffer |
|---|----------------|---------------------------------------|--------|
| A | Gate House     | User-defined edge + ratio + offset    | 8 m    |
| B | GIS            | User-defined edge + ratio + offset    | 8 m    |
| C | RAW Water Tank | User-defined edge + ratio + offset    | 8 m    |

---

### §3.3 Power Block

- Placed by `_pb_sample()` using an **asymmetric wind-direction-aware random offset** from the plot centre.
- **Placement tolerance (PB-01 rule):** How far the PB centre may drift FROM the plot centre depends on wind direction:

  | Direction relative to wind | Side axis | Max drift |
  |---------------------------|-----------|----------|
  | Windward (toward wind)    | width     | 35 % of plot width |
  | Leeward (away from wind)  | width     | 5 % of plot width  |
  | Perpendicular (both)      | length    | 20 % of plot length |

  *Goal: push PB toward the windward side, leaving the leeward zone free for Cooling Tower and Flare.*

- **Tight-site rule:** If vertical clearance on each side < 60 m, PB shifts to ±20% of site length (tight discrete choice) instead of a continuous jitter.
- 150 m × 150 m square — rotation irrelevant.
- After placement, `pb_cx, pb_cy` becomes the reference center for all later magnet logic.

---

### §3.4 PB Ring Road & Gate Spur

#### §3.4.A PB Ring Road

- Closed polyline at **14 m** from each PB face.
- Visual rule: `PB edge ←10m gap— road outer edge ——4m—→ centerline`
- **Virtual exclusion zone** placed in `placed["_pb_ring_zone"]`: inflated by `PB_RING_OFFSET + ROAD_BUFFER = 22 m` from each PB face — keeps floated blocks ≥ 8 m from ring CL.

#### §3.4.B Gate Spur Construction

Uses Gate House as the routing anchor:

1. Compute Boom Barrier midpoint (`bb_mid`) — 8 m from Gate House inner edge.
2. Project the two road-buffer corners of the selected Gate House side onto the exit line (Gate → `bb_mid`).
3. Identify `exit_helper` (unprojectable corner) and `other_corner` (projectable corner).
4. Route: **PB Ring Road → `exit_helper` → `bb_mid` → `other_corner` → Gate** (perfect 90° crossing at Boom Barrier).

#### §3.4.C Gate Death Zone

Formed when gate and Gate House share the same edge:
- Rectangle bounded by `bb_mid` and the Gate point.
- Stored as `placed["_gate_death_zone"]`.
- **Effect 1:** All floated blocks must avoid it (no blocks are allowed to overlap with this zone).
- **Effect 2:** Priority-1 snap in road cleanup skips any PB network segment inside this zone.

#### §3.4.D Ring Spur

Straight-line connector from PB Ring Road to Perimeter Fire Road.

- Side facing the gate is chosen.
- Snap start to left corner / center / right corner of ring road — whichever is closest to the Gate.
- Slides laterally (shifts 0, ±4, ±8 … ±100 m) if direct line intersects a fixed-anchor buffer.

---

### §3.5 Floated Block Placement

#### §3.5.A General Rules

- Uses `_try_magnet_place` — magnetizes to previously placed blocks at pair-appropriate gap distances.
- Tries both orientations (w×h and h×w).
- `prefer_near` → top-10% closest valid positions, then random choice.
- **Boundary Check**: Checks the block's **road buffer** (inflated by 16 m for rack blocks, 8 m for no-rack blocks) instead of its footprint. The road buffer outer edge must never exit the plot boundary (hard floor = 0 m clearance). Under relaxed bounds, the required clearance = max(0, 9 m − tol):
  - Default (tol = BOUNDARY_TOLERANCE = 10): clearance = **0 m** (buffer edge touches boundary but does not exit).
  - Strict (tol = 0): clearance = **9 m** (buffer stays fully inside, matching perimeter road CL distance).
- **Fixed anchors are excluded from default magnet targets** (Gate House, GIS, RAW Water Tank). Exception: Demi Water Tank explicitly targets RAW Water Tank.

#### §3.5.B Gap Rules between Blocks

| Pair type                  | Gap  | Rule                                        |
|----------------------------|------|---------------------------------------------|
| Rack block ↔ Rack block    | 28 m | 14 m + 14 m (shared rack-side road CL)      |
| No-rack ↔ No-rack          | 16 m | 8 m + 8 m (shared road CL)                  |
| Mixed (rack ↔ no-rack)     | 28 m | `B2B_W_RACK_OFFSET` — no shared road        |

**Rack blocks:** Power Block, Cooling Tower, WT/WWT, RAW Water Tank, Demi Water Tank, Flare.

#### §3.5.C Floated Block Order & Constraints

| # | Block          | Prefer Near        | Zone Filter       | Magnet Target   |
|---|----------------|--------------------|-------------------|-----------------|
| 1 | Cooling Tower  | PB center          | Leeward           | Power Block     |
| 2 | Flare          | Leeward corner (strict) | Leeward           | —               |
| 3 | WT/WWT         | PB center          | Near RAW Water    | Power Block     |
| 4 | Warehouse      | —                  | —                 | Power Block     |
| 5 | Admin Building | Midpoint(GH, PB)   | Near Midpoint     | Random(PB, GH)  |
| 6 | Demi Water Tank| RAW Water center   | Near RAW Water    | RAW Water Tank  |

**Leeward zone** by wind direction:

| Wind | Leeward half              |
|------|---------------------------|
| East | x ≤ 49% of site width     |
| West | x ≥ 51% of site width     |
| North| y ≤ 49% of site length    |
| South| y ≥ 51% of site length    |

**Near RAW Water filter:** block center within 150 m radius of RAW Water center.

**Near Midpoint filter:** block center within 120 m radius of the exact midpoint between Gate House and Power Block.

---

### §3.6 Pipe Rack Algorithm

Single rack type, **width = 6 m**, connects 6 "need rack" blocks: PB, Cooling Tower, WT/WWT, RAW Water Tank, Demi Water Tank, Flare. The first five form the spine/water-cluster network (§3.6.B); Flare joins via a single Case-1 stub (§3.6.C-2). (Cable Tunnel GIS↔PB is separate logic.)

#### §3.6.A Buffer Layers per Block

**Non-rack blocks** (Gate House, Warehouse, Admin, GIS) — 2 offsets:

| Key    | Offset | Meaning                                  |
|--------|--------|------------------------------------------|
| `road` | 8 m    | Road CL must be ≥ 8 m from block edge    |
| `b2b`  | 16 m   | Block-to-block edge gap                  |

**Rack blocks** (PB, Cooling Tower, WT/WWT, RAW Water Tank, Demi Water Tank, Flare) — 6 offsets per block:

| Key            | Offset | Regime    | Meaning                                        |
|----------------|--------|-----------|------------------------------------------------|
| `road_no_rack` | 8 m    | no rack   | Road CL on a side without a rack (baseline)    |
| `b2b_no_rack`  | 16 m   | no rack   | Block-to-block gap without rack (baseline)     |
| `case1_rack`   | 8 m    | with rack | Rack CL — Case 1: block → rack → road          |
| `road_w_rack`  | 16 m   | with rack | Road CL on a side that has a rack              |
| `case2_rack`   | 24 m   | with rack | Rack CL — Case 2: block → road → rack          |
| `b2b_w_rack`   | 30 m   | with rack | Block-to-block gap on a side with a rack       |

**Active case selection:**

| Block             | Case selection               |
|-------------------|------------------------------|
| Power Block       | Random: Case 1 or Case 2     |
| Cooling Tower     | Random: Case 1 or Case 2     |
| RAW Water Tank    | Always Case 1                |
| Demi Water Tank   | Always Case 1                |
| WT/WWT            | Always Case 1                |
| Flare             | Always Case 1                |

During Step 3.5 floated-block placement, only the **baseline** (no-rack) offsets are enforced. The larger "with-rack" offsets are precomputed in Step A and enforced when a rack is confirmed on a given side.

---

#### §3.6.B Spine Segments

**B-1 — PB ↔ CT Spine**

1. For PB and Cooling Tower, evaluate the distance of the selected side of Case 2's rack-buffer rectangle to the parallel plot boundary. If it is less than 10 m or if Case 2's selected side goes outside the plot boundary, choose Case 1 (even if Case 1 also goes outside). Otherwise, select randomly between Case 1 and Case 2.
   - **Overlap Exception**: If the selected rack-buffer sides of PB and CT overlap, apply the following connection rules depending on the cases chosen:
      - **PB Case 1, CT Case 2**: Draw the closest perpendicular line from the chosen PB segment (`best_pb_half`) to the CT rack buffer. Do not draw the standard "MAIN RACK" from the PB segment.
      - **PB Case 2, CT Case 1**: Draw the closest perpendicular line from the chosen CT segment (`best_ct_half`) to the PB rack buffer, and draw a perpendicular line from the CT segment to the PB center. Do not draw the standard "MAIN RACK" from the PB segment.
2. For each block, find the rack-buffer rectangle side whose outward direction points toward RAW Water Tank.
3. Divide both selected full segments by their midpoints into two half-lines each.
4. Compare all 4 combinations of half-lines, take only the 2 closest half-lines to each other as the PB and CT rack segments, and prune the not selected halves.
5. Draw a perpendicular connection from the Power Block (PB) center to the midpoint of the selected PB segment, and call this line "MAIN RACK" (it will have separate logic later, except under the overlap exception above).
6. The selected closest half-lines, any constructed perpendicular lines, and the "MAIN RACK" (if drawn) become the **PB↔CT spine centerlines**.

**B-2 — RAW Water candidate points**

1. Take RAW Water Tank's active rack-buffer rectangle — 4 corner points.
2. Prune any corner outside the plot boundary.
3. Measure distance from each remaining corner to the **center of PB's selected rack-buffer line** (from B-1).
4. Keep the **2 closest corners** as candidate RAW points.

**B-3 — Demi Water candidate points**

Same process as B-2, applied to Demi Water Tank → keep 2 candidate Demi points.

**B-4 — Pick WWT join point**

Take all 4 candidate points (2 from B-2 + 2 from B-3).

- For each point, attempt a **perpendicular projection** onto the nearest side of WWT's active rack-buffer rectangle.
- Prune projections that land outside the WWT side segment.

*If ≥ 1 projection succeeds:*
- From surviving projections, pick the **shortest source-to-WWT line**.
- WWT endpoint = kept WWT point.
- Source endpoint (on RAW or Demi):
  - If on RAW → keep it as RAW point; find closest of the 2 Demi candidates → Demi point.
  - If on Demi → keep it as Demi point; find closest of the 2 RAW candidates → RAW point.

*If no projection succeeds:*
- Take WWT rack buffer 4 corners; pick the one closest to RAW Water center → kept WWT point.
- From the 4 candidate points, pick the one closest to WWT point; apply same RAW/Demi selection rule.

**Result:** 3 points — one each on RAW, Demi, WWT rack-buffer lines → tightest water triangle.

**B-5 — Water Cluster Spine**

Connect the 3 triangle points using **orthogonal A\* paths** (no diagonals, cell size = 2 m).
- Paths may travel along any block's active rack-buffer line or through empty grid cells.
- Cannot intersect any block footprint.
- Two shortest paths of the three possible pairings are kept; the longest pair is dropped.

---

#### §3.6.C Network Connection

**C-1 — Unify into one network (two-stage BFS routing)**

1. **First connection:** Route the shortest orthogonal path from the **water cluster spine** to the closer of the two PB/CT spine lines (restricted routing: only along existing spine lines and rack-buffer edges).
2. **Second connection:** Route from the now-expanded network (water cluster + first path + hit line) to the **remaining disconnected line**.
   - Fallback: if restricted routing fails, open the grid fully and re-route.

Both passes must:
- Extend an existing spine line, OR route along another rack block's active rack-buffer line.
- Never cross any block footprint.

**C-2 — Flare Pipe Rack Connection**

1. If any existing rack segment already touches the Flare's active rack-buffer rectangle → connection satisfied.
2. Otherwise:
   - Take the 4 corners of Flare's active rack-buffer rectangle.
   - For each corner, find an orthogonal path to the unified rack network.
   - Select the corner that yields the **shortest real-path distance** (obstacle-aware, not straight-line).
   - Add this path to the unified network.

**Rack output:** Single connected rack polyline network (centerlines, 6 m wide). Becomes an obstacle for subsequent road placement.

---

### §3.7 Perimeter Fire Road (Union of Buffers Contour)

Instead of heuristic intersections, the perimeter fire road is generated mathematically by tracing the boolean union of all block road buffers.

#### §3.7.A Buffer Inflation
Each placed block is expanded outward by its required road offset:
- **Rack Blocks:** 16 m offset.
- **No-Rack Blocks:** 8 m offset.

This generates an axis-aligned buffer rectangle around every block.

#### §3.7.B Grid-Based Boolean Union
A high-resolution 2D integer grid is created over the plot bounds. The buffer rectangle of every block is "painted" onto this grid (setting cells to 1). This effectively performs a geometric boolean union of all required road stand-offs, forming a single continuous footprint.

**Gate Death Zone Extension ("Don't Allow Perimeter Road" Zone):**
To prevent the perimeter road from creating detours in the space between the gate and the Gate House, the "Don't Allow Perimeter Road" zone is defined strictly as the bounding box starting from the gate point and extending to the farthest corner of the Gate House's 8m road buffer.
- This zone is painted onto the grid as a solid block.
- **Combined-Block Routing**: If this zone intersects with the road buffer of any other blocks (such as the Admin Building or Warehouse), the code computes the transitive closure of all overlapping block buffers and merges them with the zone into a single combined block. This combined block is carved as a single unit touching the gate-side boundary, forcing the perimeter road contour to route entirely below all merged blocks (closer to the plot center) rather than passing between them.

**Buffer Sorting Priority:**
When processing buffers for the perimeter generation, they are explicitly sorted so that the Gate House is processed last. This ensures its priority over other buffers when resolving intersections near the gate.

#### §3.7.C Contour Tracing (The Perimeter Road)
A flood-fill algorithm runs from the outside of the grid to identify all "exterior" empty cells. 
The boundary edges between the exterior (empty) cells and the interior (filled) cells are extracted. These edges are merged into contiguous orthogonal line segments. 

**Boundary Collision Carve-out:** If a block is placed so close to the plot boundary that its road buffer extends to or beyond the plot edge (or touches the Gate Death Zone / Gate House), the algorithm will actively "carve out" the boundary-facing side of the buffer from the grid. This prevents the flood-fill from getting cut off at the plot boundary (which would cause the road to cut straight through the block). Instead, the flood-fill enters the carved-out area, forcing the perimeter road to route smoothly around the **inner** buffer of the block.

> [!NOTE]
> Blocks are permitted to sit right at the plot boundary (road buffer touches boundary = 0 m clearance). They are **not** permitted to have their road buffer exit the plot. This is enforced during magnet placement by `_within_relaxed_bounds`.

The resulting polyline is mathematically guaranteed to be a closed, continuous, and non-intersecting loop that perfectly hugs the facility at the exact required stand-off distances (8m or 16m), forming the final **Outer Perimeter Loop**.


## §3.8 Road Access by Block

### §3.8.A Special Cases

| Block       | Road   | Access Points                  | Notes                            |
|-------------|--------|--------------------------------|----------------------------------|
| Gate House  | 8m     | 1 — the gate itself            | Gate IS the access point         |
| Power Block | 8m     | 4 corners of PB Ring Road      | Ring road serves as access       |

### §3.8.B Group A — 8m Road Connections

| #  | Block         | Count | Corner Selection Rule                                               |
|----|---------------|-------|---------------------------------------------------------------------|
| 2  | GIS           | 2     | Corner near boundary + corner near PB (diagonal opposite)          |
| 3  | RAW Water     | 1     | Boundary corner **furthest from Demi Water Tank**                  |
| 5  | Cooling Tower | 2     | Corner near boundary + corner near PB (diagonal opposite)          |
| 6  | WT/WWT        | 1     | Corner nearest to plot boundary                                     |
| 7  | Warehouse     | 2     | Corner near boundary + corner near PB (diagonal opposite)          |
| 9  | Admin         | 1     | Corner nearest to Gate House                                        |

**Total:** 9 × 8m connections across 6 blocks.

### §3.8.C Group B — 6m Road Connections

6m roads represent lower-traffic secondary access (rack corridors, chemical delivery, maintenance).

| #  | Block         | Count | Access Point Position                             | Notes                                    |
|----|---------------|-------|---------------------------------------------------|------------------------------------------|
| 3  | RAW Water     | 1     | Corner near WT/WWT                                | Chemical/maintenance delivery            |
| 6  | WT/WWT        | 1     | Corner near RAW Water                             | Truck-heavy chemical delivery on 8m side |
| 8  | Flare         | 1     | Corner on plant-facing side only                  | NEVER boundary/leeward (radiation)       |
| 9  | Admin         | 1     | Corner opposite to Gate                           |                                          |
| 10 | Demi Water    | 1     | Corner near pump skid (PB-facing)                 | Low-traffic, single access               |

**Total:** 5 × 6m connections across 5 blocks.

### §3.8.D Complete Access Summary

| #  | Block          | 8m | 6m | Total | Key Constraint                                 |
|----|----------------|----|----|-------|------------------------------------------------|
| 1  | Gate House     | 1  | 0  | 1     | Gate = access                                  |
| 2  | GIS            | 2  | 0  | 2     | Boundary corner + PB corner                    |
| 3  | RAW Water      | 1  | 1  | 2     | 8m: far from Demi; 6m: near WT/WWT            |
| 4  | Power Block    | 1  | 0  | 1     | Ring road = access (4 corners)                 |
| 5  | Cooling Tower  | 2  | 0  | 2     | Boundary + PB corners                          |
| 6  | WT/WWT         | 1  | 1  | 2     | 8m: near boundary; 6m: near RAW Water          |
| 7  | Warehouse      | 2  | 0  | 2     | Boundary + PB corners                          |
| 8  | Flare          | 0  | 1  | 1     | Plant-facing only; NEVER leeward/boundary       |
| 9  | Admin          | 1  | 1  | 2     | 8m: near Gate; 6m: opposite corner             |
| 10 | Demi Water     | 0  | 1  | 1     | Near pump skid (PB-facing)                     |

---

## §4. Step 1 Output Dictionary

```python
{
    "blocks":                list[dict],   # name, x, y, width, height, color, rotated
    "boom_barrier":          list[tuple],  # 16m line from Gate House inner edge
    "ring_road":             list[tuple],  # PB ring road closed polyline
    "perimeter_segments_raw":list[seg],    # B-1 raw perimeter segments
    "group_a_segments_raw":  list[seg],    # A-2 raw Group A access segments
    "all_segments_cleaned":  list[seg],    # B-2 cleaned merged result
    "gate_spur":             list[tuple],  # gate → ring road polyline
    "ring_spur":             list[tuple],  # ring road → perimeter road polyline
    "rack_buffers":          dict,         # {block_name: {offset_key: rect}}
    "rack_segments":         list[seg],    # unified rack network centerlines
    "rack_candidates":       list[tuple],  # RAW/Demi candidate corner points
    "active_rack_cases":     dict,         # {block_name: "case1_rack"|"case2_rack"}
    "water_triangle":        list[tuple],  # 3 points: RAW, Demi, WWT on rack buffers
    "gate_point":            tuple,        # (x, y) gate midpoint on boundary
    "gate_death_zone":       tuple|None,   # (x, y, w, h) or None
    "pb_center":             tuple,        # (pb_cx, pb_cy)
    "cell_size":             int,          # 2
    "block_buffer":          int,          # 16
    "pb_ring_offset":        int,          # 14
    "perimeter_cl":          float,        # 9.0
}
```

All roads are **sketch roads** — centerlines only (lines). No physical width rendered yet.

## §5. Refine Modes (Step 2, Step 3, Step 4)

> Executed interactively after the user selects their favorite layouts from Step 1.

### Step 2: Detailing and Subdividing
1. **Place small blocks** — the remaining small and variable blocks are added around the committed roads and large blocks from Step 1.
2. **Subdivide large blocks** — major blocks are split into detailed individual buildings.
3. **Add building entrances and access roads** — each building gets a door facing the nearest road, and short access stubs are routed.
4. **User Selection** — the user reviews the detailed layouts and selects the top 3.

### Step 3: Variation and Mutation
1. **Generate variations** — slightly mutate and perturb the layouts selected in Step 2 to create similar alternatives (no new elements are added).
2. **Micro-adjustments** — allows the user to find the perfectly refined version of their chosen layout.
3. **User Selection** — the user finalizes the top 1~3 layouts.

### Step 4: Final Export
1. **Rule Verification** — a final pass of all constraints and penalty scoring.
2. **CAD Export** — the finalized 1~3 layouts are exported as accurate DXF CAD drawings.

---

## §6. Key Differences from Phase 05

| Aspect              | Phase 05                              | Phase 06                                          |
|---------------------|---------------------------------------|---------------------------------------------------|
| Coordinate system   | Continuous float (metres)             | Snapped to 2m grid                                |
| Road creation       | A* from gate to each building entrance| Road graph first; blocks placed around it         |
| Building entrances  | Required for routing                  | Not used in Step 1; deferred to Step 2            |
| Ring Road           | Hand-injected geometry segment        | Native graph edge, merges where overlapping       |
| Road classification | Single type                           | Primary (fire) / Secondary (stubs) / Access (S2) |
| Block buffers       | Fixed 15m all sides                   | 8m default; 14m on rack sides                     |
| Perimeter road shape| Rectangle only                        | Polygon — 4–6+ sides, generated from buffers      |
| Perimeter setback   | Hard-coded                            | `PERIMETER_SETBACK` configurable constant         |

---

## §7. Constants Quick Reference

```python
CELL_SIZE          = 2    # metres per grid cell
ROAD_BUFFER        = 8    # road CL from non-rack block edge
BLOCK_BUFFER       = 16   # min block-to-block gap (no rack)
BOUNDARY_MARGIN    = 17   # min dist: floated block → site boundary
BOUNDARY_TOLERANCE = 10   # relaxed bound for tight fits
PB_RING_OFFSET     = 14   # PB ring road CL from PB face
PERIMETER_SETBACK  = 5    # perimeter road outer edge from boundary
PERIMETER_ROAD_W   = 8    # perimeter road width
PERIMETER_CL_DIST  = 9    # = SETBACK + ROAD_W / 2

RACK_WIDTH         = 6    # pipe rack width
ROAD_W_RACK_OFFSET = 14   # road CL on a rack side
B2B_W_RACK_OFFSET  = 28   # block-to-block on a rack side
RACK_CASE1_OFFSET  = 6    # rack CL: Case 1 (block → rack → road)
RACK_CASE2_OFFSET  = 22   # rack CL: Case 2 (block → road → rack)
```

# PowerPlan AI — Layout_Gen_Design

> **Single source of truth for this project.** Consolidates the former Product
> Vision, the full Stage 1 structured plan, the methodology/UX guide, and the
> rule reference. Older phase notes and the previous (Phase 03–05) code pipeline
> live under [`_Archive/`](_Archive/) for history; they are **not** part of the
> working system.

---

# PART 0 — THE NEW PLOT SHAPE (read this first)

## 0.1 What changed, in simple words

- The plot used to be a **rectangle**, described by just **width and length**.
- Now the plot is a **polygon** — a shape made of **straight sides** (up to 6),
  and the sides can be **diagonal**.
- A **rectangle is still allowed** — it is simply a polygon with 4 corners.
- **You draw the plot in CAD** and the program reads the shape from the file.
- The **only setting on the screen** is now the **wind direction**. Everything
  else (gate, gate house, GIS, RAW tank, boom) comes from the drawing.

## 0.2 The plot helper — `Core/Plot.py`

All the shape math lives in one new file, [`Core/Plot.py`](Core/Plot.py). It can
answer these questions about the plot:

- **Is a point inside the plot?**
- **Is a whole block inside the plot?** (and how far it may stick out)
- **Where is the plot center?**
- **How far is a point from the nearest side?**
- **Shrink the plot inward by N metres** — used to make the perimeter fire road.
- **Move the whole plot** — used when the layout is re-centered.

> [!IMPORTANT]
> **Why this is safe.** For a **rectangle**, the new helper gives the **exact same
> answer** as the old rectangle code. We proved it with an automatic test over
> **23,820 cases** — every one matches. So using the polygon **cannot change** how
> rectangles behave. New diagonal plots get the new behavior; old rectangles stay
> identical.

## 0.3 Reading the CAD file — `Core/CADImport.py`

The program reads the drawing with [`Core/CADImport.py`](Core/CADImport.py).
Each item must be on its **own layer**, named exactly:

| Layer in the drawing       | What you draw     | What it becomes                     |
|----------------------------|-------------------|--------------------------------------|
| `Plot`                     | one closed outline (up to 6 corners) | the plot shape    |
| `Gate`                     | a **circle**      | the gate point (the circle's center) |
| `Gate House`               | a rectangle       | the gate house building              |
| `RAW Tank`                 | a **circle**      | the RAW water tank                   |
| `GIS`                      | a rectangle       | the GIS building                     |
| `Gate House Boom Barrier`  | a **line**        | the boom barrier                     |

The reader also **fixes common problems by itself**:

- **Units.** If the drawing is in **millimetres**, it converts everything to
  **metres** automatically (it checks the GIS size, which should be 110 × 51 m).
- **Position.** It **moves the drawing so it starts at (0,0)**.
- **Circles.** Tanks drawn as circles are read correctly.
- **Warnings.** If a layer is missing, or something was left on the wrong layer
  (for example on layer `0`), it shows a **warning** but does not crash.

## 0.4 Checked against your real drawing

Your file `Data/sample_plot.dxf` was tested and read correctly:

- A **5-sided plot** (a rectangle with one diagonal corner), **512 × 280 m**.
- Units read as **millimetres** and converted to metres.
- The **gate is exactly on the boundary**.
- Gate House (12×12), GIS (110×51), RAW Tank (37×37) are the **right size** and
  **inside the plot**.

> [!NOTE]
> **One surprise:** your **gate is on a diagonal side**, but the boom barrier is
> drawn straight. So later (Phase 5) the gate road must handle a boom on a
> diagonal side. This is written down so we don't forget.

---

# PART I — PRODUCT

## 1. Vision & Goal

Automate the generation of power-plant **Plot Plans**: optimise the placement of
60+ buildings on a site from engineering constraints and rules. Target a compact
layout on narrow sites, with controlled flexibility to exceed boundaries when
necessary. Every result is meant to be verified against existing reference
drawings for real-world viability.
- **[Polygon change]** Sites can now be **real-shaped plots with diagonal sides**, not only rectangles.

**Tech stack:** Obsidian (organisation) · VS Code (engine) · **Python** ·
**Matplotlib** (visualisation) · **Streamlit** (web dashboard) · **ezdxf** (reading CAD files). The engine is
deliberately UI-free so it can later be wrapped by Streamlit (now) or ported to a
**C# / PyRevit add-in** (future) — see [Part IV](#part-iv--code--roadmap).

**Key features:** interactive site setup · rule-based grouping · automated penalty
scoring · generative layouts (100+ iterations) · DXF export · reference-drawing
verification.

## 2. Status & Phase Roadmap

| Phase | Title | Status |
|-------|-------|--------|
| 01 | The Empty Plot (site boundary + dashboard) | ✅ Done |
| 02 | The Three Giants (PB, CT, Admin) | ✅ Done |
| 03 | Engineering Rules (penalty scoring engine) | ✅ Done |
| 04 | 12 groups, generic rule engine, rule network | ✅ Done |
| 05 | Advanced routing & sequential placement | ✅ Done |
| 06 | Grid-first generative layout (current) | ✅ Done |
| P | Polygon plot migration | ✅ Done |

The working engine is [`Core/Stage01.py`](Core/Stage01.py), driven by the
[`Dashboard/WebDashboard01.py`](Dashboard/WebDashboard01.py) Streamlit app.

## 3. Methodology

**Grid-first** — every block, road centerline and rack path snaps to a 2 m grid
(`snap(v) = round(v/2)*2`), shrinking the search space versus continuous coords.

**3-pass boundary tolerance** — if a tight site can't satisfy every rule, the
engine retries with relaxing bounds:
- **Pass 1 (strict):** ≥18 m interior safety margin (`boundary_tol = -18`).
- **Pass 2 (standard):** fully inside the plot (`boundary_tol = 0`).
- **Pass 3 (tight):** allow select blocks up to 10 m past the boundary (`boundary_tol = +10`).
- **[Polygon change]** This "inside / outside" check is now done against the **polygon** (including diagonal sides), not the rectangle.

**Multi-stage refinement** — A four-stage interactive generative system (Generate & Refine modes) where every stage pairs a layout **image** with a rule **score** for decision support:

- **Stage 1 (Generate Mode):** Automatically generates 100+ layout alternatives focusing on core large blocks. User selects the top 3 favorites to refine.
- **Stage 2 (Refine Mode – Detailing):** Places remaining small blocks based on the 3 selected layouts and subdivides large blocks into detailed individual buildings. User selects the top 3 detailed layouts.
- **Stage 3 (Refine Mode – Variation):** Generates slightly mutated, similar variations of the selected layouts from Stage 2 without adding new elements. User finalizes the top 1~3 layouts.
- **Stage 4 (Final Export):** Verifies all constraints and outputs the final 1~3 layouts as CAD drawings (DXF).

---

# PART II — STAGE 1 TECHNICAL SPEC

**Stage 1 Scope:** In this stage, we place all the core large blocks and generate the skeleton of the infrastructure. The algorithm executes a block-first workflow where blocks are placed, followed by the pipe rack network, and finally the perimeter and access roads are routed around them.

Specifically, Stage 1 accomplishes the following:
1. **Reads CAD Anchors:** Extracts the custom polygon plot, gate point, Gate House, GIS, RAW tank, and boom barrier directly from the drawing on disk.
2. **Generates Core Layouts:** Places the Power Block (wind-aware centroid shift) and floats the remaining blocks (Cooling Tower, WT/WWT, Warehouse, Flare, Admin, Demi Water) using a randomized magnet scan constraint-checked against the polygon.
3. **Routes Pipe Racks:** Generates a unified 6 m pipe rack spine and water cluster network connecting the key blocks.
4. **Traces Perimeter Road:** Traces the outer perimeter fire road loop by performing a morphological union of all block buffers clamped to the plot polygon.
5. **Re-centers Plot:** Slides the plot polygon corners to center the finalized layout, returning a complete sketch dictionary.

## §1. Block Catalog

| #  | Block Name       | Contents                                                          | Notes                     |
|----|------------------|------------------------------------------------------------------|---------------------------|
| 1  | Power Block      | GT Bldg, ST Bldg, HRSG, Control Bldg, Main Stack, Transformers   | Central anchor — first    |
| 2  | GIS              | 345kV GIS, GIS Control Bldg                                       | Near NE boundary          |
| 3  | Cooling Tower    | Cooling Tower, CW Pump, CT Electrical                            | Leeward zone              |
| 4  | Flare            | Flare Stack, Flare KO Drum, N₂ for Flare                        | Leeward corner            |
| 5  | WT/WWT           | WT/WWT Bldg, Chemical Storage, Clarifiers, WT/WWT Pump Room      | Downwind                  |
| 6  | RAW Water Tank   | RAW Water Tank, Buffer Pond, Supply Pump                         | Near water tie-in         |
| 7  | Demi Water Tank  | Demi Water Tank, Potable Water Tank                             | Near RAW Water            |
| 8  | Admin Building   | Admin Bldg, Parking                                             | Near Gate                 |
| 9  | Gate House       | Gate House                                                      | Fixed on boundary         |
| 10 | Warehouse        | Machine Shop & Warehouse, AUX/LPG Boiler, Oil Storage          | Near boundary road        |

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

## §2. Grid & Coordinate System

| Constant             | Value    | Meaning                                      |
|----------------------|----------|----------------------------------------------|
| `CELL_SIZE`          | 2 m      | Metres per grid cell                         |
| `ROAD_BUFFER`        | 8 m      | Min distance from block edge to road CL      |
| `BLOCK_BUFFER`       | 16 m     | Min gap between two block edges (no rack)    |
| `BOUNDARY_TOLERANCE` | 10 m     | Leeway for tight border fits                 |
| `PB_RING_OFFSET`     | 16 m     | PB ring road CL from PB face *(see note)*    |
| `PERIMETER_SETBACK`  | 5 m      | Perimeter road outer edge from plot boundary |
| `PERIMETER_ROAD_W`   | 8 m      | Perimeter road width                         |
| `PERIMETER_CL_DIST`  | 9 m      | Perimeter road CL from boundary (5 + 8/2)   |

All block positions snap to the 2m grid (`snap(v) = round(v / 2) * 2`).
- **[Polygon change]** The grid covers the **box around the polygon**. Grid squares that fall **outside the polygon** are blocked, so roads and racks **cannot cross a diagonal cut-off corner**.
- **Temporary Plot Boundary (DXF Offset):** When loading a plot polygon from a DXF file, the boundary is automatically inset by `PERIMETER_SETBACK` (5 m) to form a **temporary plot boundary**. All subsequent engine logic (placement, containment checks, routing, and recentering) operates on this temporary plot boundary to ensure block footprints maintain sufficient distance from the actual boundary. The original boundary is carried alongside as `plot_polygon_original` (and `Plot.original_plot`, which `Plot.translate` shifts in lockstep so recentering moves both). The dashboard shows the original boundary in black, with a checkbox to toggle visibility of this temporary boundary in blue dashed lines.
  - **Origin invariant:** the engine assumes the **active** plot (the inset) is origin-normalised — `plot.bbox == (0, 0, sw, sl)` with `sw, sl = plot.size`. Insetting moves the bbox inward to ~(5, 5), so `CADImport` re-normalises after insetting: it shifts the inset back to the origin and moves the original boundary, gate, boom and anchors by the same amount. The original boundary therefore sits ~5 m *outside* the inset (slightly negative coords). Skipping this re-normalisation breaks the grid/containment alignment and yields **no layout at all**.

> **Note on `PB_RING_OFFSET`:** the original plan text specified 14 m; the working
> engine (`Core/Stage01.py`) uses **16 m**. The engine value is authoritative.

## §3. Step 1 — Block + Road + Rack Sketch

### §3.1 Master Placement Sequence

```
1.  Fixed anchors        →  Gate House, GIS, RAW Water Tank   [from the drawing]
2.  Power Block          →  Plot center ± wind jitter
3.  PB Ring Road         →  Geometry drawn; corridor locked for floated-block placement
4.  Gate Spur + Ring Spur→  Both spurs built from fixed anchors before floated blocks [from the drawing]
5.  Boom Barrier         →  Read from the drawing              [from the drawing]
6.  Floated blocks       →  Cooling Tower, WT/WWT, Warehouse, Flare, Admin, Demi Water
7.  Pipe Rack            →  6m rack network (§3.6) — before access roads
8.  Access Road Part 1   →  Midpoint connection from block buffer to road network (§3.7.A)
9.  Access Road Part 2   →  Perimeter loop around block buffer rectangle (§3.7.B)
10. Recenter             →  Move plot + gate to content bbox center (§3.8) [moves the polygon]
```

### §3.2 Fixed Anchor Placement — **[Polygon change]**

- Gate House, GIS, and RAW Water Tank are **read from the drawing** as real positions. There are **no more screen sliders** for them.
- They are grid-snapped and checked to be strictly **inside the plot** (using the new polygon check).
- In the legacy rectangle fallback mode, fixed anchors use `place_anchor(sw, sl, name, edge, ratio, offset)` — result is grid-snapped and clamped to plot bounds.

| # | Block          | Position Rule                         | Buffer |
|---|----------------|---------------------------------------|--------|
| A | Gate House     | User-defined edge + ratio + offset    | 16 m   |
| B | GIS            | User-defined edge + ratio + offset    | 8 m    |
| C | RAW Water Tank | User-defined edge + ratio + offset    | 8 m    |

#### §3.2.1 How much each block MOVES per generation (jitter rules)

Every time you press **Generate Layouts**, some blocks shift a little so you get different options. This table is the **single source of truth** for that movement:

| Block | Moves each generation? | Rule |
|-------|------------------------|------|
| **Power Block** | ✅ Yes | wind-aware shift from the **plot center** — windward **35%**, leeward **5%**, sideways **20%** of the plot size (see §3.3) |
| **Gate House** | ❌ **No (fixed)** | stays exactly at its CAD position |
| **Boom Barrier** | ❌ **No (fixed)** | attached to the Gate House, so it stays put too |
| **GIS** | ❌ No (fixed) | stays exactly at its CAD position |
| **RAW Water Tank** | ✅ Yes | **±5%** of the plot size around its CAD position |
| **Cooling Tower** | ✅ Yes | no fixed jitter — sticks to the Power Block in the leeward zone, so it moves as the Power Block moves |
| **WT/WWT** | ✅ Yes | sticks to the Power Block, near RAW Water |
| **Warehouse** | ✅ Yes | sticks to the Power Block |
| **Admin Building** | ✅ Yes | placed between Gate House and Power Block |
| **Demi Water Tank** | ✅ Yes | sticks to the RAW Water Tank |
| **Flare** | ✅ Yes | placed at the leeward **corner of the plot** |

> [!NOTE]
> **Why Gate House and boom are fixed.** The boom barrier is drawn touching the gate house. If the gate house jittered, the boom would float away from it. So the gate house (and its boom) are kept fixed; only RAW Water Tank still jitters among the CAD anchors.

### §3.3 Power Block

- Placed by `_pb_sample()` using an **asymmetric wind-direction-aware random offset** from the plot centre.
- **Placement tolerance (PB-01 rule):** How far the PB centre may drift FROM the plot centre depends on wind direction:

  | Direction relative to wind | Side axis | Max drift |
  |---------------------------|-----------|----------|
  | Windward (toward wind)    | width     | 35 % of plot width |
  | Leeward (away from wind)  | width     | 5 % of plot width  |
  | Perpendicular (both)      | length    | 20 % of plot length |

  *Goal: push PB toward the windward side, leaving the leeward zone free for Cooling Tower and Flare.*
- **[Polygon change]** "Plot center" now means the **polygon center** (centroid/average), and the "inside the plot" collision checks use the polygon bounds.

- **Tight-site rule:** If vertical clearance on each side < 60 m, PB shifts to ±20% of site length (tight discrete choice) instead of a continuous jitter.
- 150 m × 150 m square — rotation irrelevant.
- After placement, `pb_cx, pb_cy` becomes the reference center for all later magnet logic.

### §3.4 PB Ring Road & Gate Spur

#### §3.4.A PB Ring Road

- Closed polyline at **16 m** from each PB face (`PB_RING_OFFSET`).
- Visual rule: `PB edge ←10m gap— road outer edge ——4m—→ centerline`
- **Virtual exclusion zone** placed in `placed["_pb_ring_zone"]`: inflated by `PB_RING_OFFSET + ROAD_BUFFER` from each PB face — keeps floated blocks ≥ 8 m from ring CL.

#### §3.4.B Gate Spur Construction

Uses Gate House as the routing anchor:

1. Compute Boom Barrier midpoint (`bb_mid`) — 8 m from Gate House inner edge.
2. Project the two road-buffer corners of the selected Gate House side onto the exit line (Gate → `bb_mid`).
3. Identify `exit_helper` (unprojectable corner) and `other_corner` (projectable corner).
4. Route: **spur_start → `exit_helper` → `bb_mid` → `other_corner` → Gate** (perfect 90° crossing at Boom Barrier).
- **[Polygon change]** the boom side (N/S/E/W) and midpoint are taken from the **CAD boom line**, so the road crosses the boom exactly where it is drawn.

#### §3.4.C Gate Death Zone

Formed when gate and Gate House share the same edge:
- Rectangle bounded by `bb_mid` and the Gate point.
- Stored as `placed["_gate_death_zone"]`.
- **Effect 1:** All floated blocks must avoid it (no blocks are allowed to overlap with this zone).
- **Effect 2:** Priority-1 snap in road cleanup skips any PB network segment inside this zone.

#### §3.4.D Ring Spur

Orthogonal connector from PB Ring Road corner to `exit_helper`, then continues as Gate Spur.

- **Start point (`spur_start`):** pick the ring road **corner** (one of 4) closest to `exit_helper` — no midpoints.
- **Exit_line axis:** horizontal (`y = exit_helper.y`) for N/S boom edge; vertical (`x = exit_helper.x`) for E/W boom edge.
- **L-route** (2 axis-aligned segments):
  - Strictly use Option A (project `spur_start` onto exit_line): `turn_pt = (sx, ehy)` [N/S] / `(ehx, sy)` [E/W]. This extends the vertical edge of the ring road for N/S booms, and the horizontal edge for E/W booms.
- Ring spur path: **`spur_start → turn_pt → exit_helper`**
- **[Polygon change] Ring-spur connection rule.** When `exit_helper` falls **within** the ring road's x/y span → a clean straight projection drops onto the nearest ring edge (original behaviour). When `exit_helper` is **outside** the span → the ring spur routes an **L from the closest ring corner** with a **perpendicular final approach**, which guarantees it connects to the ring road (instead of landing just off it).

### §3.5 Floated Block Placement

#### §3.5.A General Rules

- Uses `_try_magnet_place` — magnetizes to previously placed blocks at pair-appropriate gap distances.
- Tries both orientations (w×h and h×w).
- `prefer_near` → top-10% closest valid positions, then random choice.
- **Boundary Check — [Polygon change]:** Checks the block's **road buffer** (inflated by 16 m for rack blocks, 8 m for no-rack blocks) instead of its footprint. The road buffer outer edge must never exit the plot boundary. In polygon mode, this check is done against the **polygon boundary** (including diagonal sides, hard floor = 0 m clearance). Under relaxed bounds, the required clearance = max(0, 9 m − tol):
  - Default (tol = BOUNDARY_TOLERANCE = 10): clearance = **0 m** (buffer edge touches boundary but does not exit).
  - Strict (tol = 0): clearance = **9 m** (buffer stays fully inside, matching perimeter road CL distance).
- **Fixed anchors are excluded from default magnet targets** (Gate House, GIS, RAW Water Tank). Exception: Demi Water Tank explicitly targets RAW Water Tank.

#### §3.5.B Gap Rules between Blocks

| Pair type                  | Gap  | Rule                                        |
|----------------------------|------|---------------------------------------------|
| Rack block ↔ Rack block    | 32 m | 16 m + 16 m (`ROAD_W_RACK_OFFSET` each)     |
| No-rack ↔ No-rack          | 16 m | 8 m + 8 m (`ROAD_BUFFER` each)              |
| Mixed (rack ↔ no-rack)     | 24 m | 16 m + 8 m                                  |

**Rack blocks:** Power Block, Cooling Tower, WT/WWT, RAW Water Tank, Demi Water Tank, Flare.

#### §3.5.C Floated Block Order & Constraints

| # | Block          | Prefer Near        | Zone Filter       | Magnet Target   |
|---|----------------|--------------------|-------------------|-----------------|
| 1 | Cooling Tower  | PB center          | Leeward           | Power Block     |
| 2 | Flare          | Leeward corner (strict) | Leeward      | —               |
| 3 | WT/WWT         | PB center          | Near RAW Water    | Power Block     |
| 4 | Warehouse      | —                  | —                 | Power Block     |
| 5 | Admin Building | Midpoint(GH, PB)   | Near Midpoint     | Random(PB, GH)  |
| 6 | Demi Water Tank| RAW Water center   | Near RAW Water    | RAW Water Tank  |

> [!NOTE]
> **Placement fallback chain.** Each floated block (`_try_magnet_place`) tries, in order: (1) magnetize to its **specified** magnet target within the zone filter; (2) magnetize to **any** placed block; (3) **empty-space** scan — a coarse grid over the whole plot, picking any collision-free, in-bounds spot (zone filter preferred, dropped if nothing in-zone fits). Only if all three fail does the block return `None` and the whole layout attempt is discarded and retried. `prefer_near` (top-10%-closest) still applies across whichever candidate set wins, so blocks cluster near their anchor.

> [!NOTE]
> **Flare corner placement — [Polygon change].** Unlike other blocks (which use the magnet placement engine), the `Flare` bypasses magnetization entirely. It is placed directly in one of the leeward **corners of the polygon** (prioritizing bottom-left, top-left, bottom-right, or top-right depending on the wind direction `wind_dir`). It calculates grid-snapped and clamped coordinates matching the active pass tolerance (`_pass_tol` or `BOUNDARY_TOLERANCE` fallback) and runs collision checks against already placed blocks.

**Leeward zone — [Polygon change]** by wind direction. The leeward half is now the half of the plot on the downwind side of the **plot center** (polygon center):

| Wind | Leeward half              |
|------|---------------------------|
| East | x ≤ 49% of site width     |
| West | x ≥ 51% of site width     |
| North| y ≤ 49% of site length    |
| South| y ≥ 51% of site length    |

**Near RAW Water filter:** block center within 150 m radius of RAW Water center.

**Near Midpoint filter:** block center within 120 m radius of the exact midpoint between Gate House and Power Block.

### §3.6 Pipe Rack Algorithm

Single rack type, **width = 6 m**, connects 6 "need rack" blocks: PB, Cooling Tower, WT/WWT, RAW Water Tank, Demi Water Tank, Flare. The first five form the spine/water-cluster network (§3.6.B); Flare joins via a single Case-1 stub (§3.6.C-2). (Cable Tunnel GIS↔PB is separate logic.)

> [!NOTE]
> **[Polygon change] Racks stay inside the plot.** Every rack routing grid now blocks all cells **outside the polygon** (`_mask_grid_to_plot`), so a rack can **never cross a diagonal/cut corner**. (The grids are re-masked after each reset inside `mark_b1_grids`, since the reset wiped the mask.)

> [!NOTE]
> **Rack ↔ road-buffer clearance rule.** A rack path may **cross** a block's road buffer perpendicularly, but may **not run parallel along it** within **9 m** (`RACK_ROAD_CLEARANCE`). The block's own rack-buffer corridors (`case1` / `case2`) are **exempt** — those are the intended rack lanes. Enforced as a direction-aware move filter in both routers (the connector A\* and the water-cluster `astar` via its `forbid_move` hook). This keeps connectors out of road corridors while still letting them reach a block's rack buffer.

> [!NOTE]
> **Buffer-corridor routing rule.** A rack path may **not** cut through the gap between a block's footprint and its active rack-buffer line — if a block is in the way, the path must run **on** the rack-buffer line. Enforced by `mark_rack_obstacles`, which blocks each rack block's footprint inflated to one grid cell *inside* its active buffer line (leaving the buffer-line ring free for travel). Applied to every rack routing grid (PB↔CT connect B-1, water-cluster B-5, network connect C-1, Flare C-2). Routing degrades gracefully: the network/flare router (`route_between`) tries **restricted** (buffer-lines & spines only) → **inflated full grid** (buffer-corridor) → **footprint-only full grid** as a last resort; B-1/B-5 try **inflated** → **footprint-only**.

#### §3.6.A Buffer Layers per Block

**Non-rack blocks** (Warehouse, Admin, GIS) — 2 offsets:

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
| Power Block       | Rand/Rule: Random, but falls back to Case 1 if Case 2's side is < 10m from boundary or goes outside |
| Cooling Tower     | Rand/Rule: Random, but falls back to Case 1 if Case 2's side is < 10m from boundary or goes outside |
| RAW Water Tank    | Always Case 1                |
| Demi Water Tank   | Always Case 1                |
| WT/WWT            | Always Case 1                |
| Flare             | Always Case 1                |

During Step 3.5 floated-block placement, only the **baseline** (no-rack) offsets are enforced. The larger "with-rack" offsets are precomputed in Step A and enforced when a rack is confirmed on a given side.

**Power Block Unrackable Sides Optimization:**
For the Power Block, the sides that do not intersect any created rack path (both spine and connection segments) are classified as "unrackable" sides. On these unrackable sides:
* The road buffer offset is reduced from the rack standard of 16 m to the baseline of **8 m**.
* The block-to-block buffer offset is reduced to the baseline of **16 m**.
* The PB ring road centerline shrinks on these sides to an **8 m** offset.
* Any floated blocks magnetized to the PB on these unrackable sides are shifted by **8 m** towards the PB center (matching the 16 m → 8 m road-buffer reduction on that side).

> [!WARNING]
> **Implementation note (known limitation).** This optimization runs *before* the connection segments are routed, so the side classification currently inspects **spines only**, not connection segments. A side reached only by a *connector* can therefore be mis-classified as unrackable and wrongly reduced. Detecting it correctly requires running the side check against the fully-routed rack network (build network → detect → optimize → rebuild). Not yet implemented — see session notes.

#### §3.6.B Spine Segments

**B-1 — PB ↔ CT Spine**

1. For PB and Cooling Tower, evaluate the distance of the selected side of Case 2's rack-buffer rectangle to the parallel plot boundary. If it is less than 10 m or if Case 2's selected side goes outside the plot boundary, choose Case 1 (even if Case 1 also goes outside). Otherwise, select randomly between Case 1 and Case 2.
   - *Note:* the "selected side" here is only a clearance **probe** (the RAW-facing side, via `get_spine_side`) used to measure boundary distance for the case decision. The side actually used for the spine is chosen separately in step 2, after the case is fixed.
   - **Overlap Exception:** If the selected rack-buffer sides of PB and CT overlap, apply the following connection rules depending on the cases chosen:
       - **PB Case 1, CT Case 2:** Draw **one straight perpendicular line** along the MAIN RACK axis (through the PB center `(pb_cx, pb_cy)`, perpendicular to the overlapping sides) spanning from the **PB center** to **CT's Case 1 rack-buffer line**. Split it at the overlapped PB/CT side into **two separate segments**: the **PB center → overlap** part is the **MAIN RACK**, and the **overlap → CT Case 1 buffer** part is the CT connector. Keep them separate (the MAIN RACK takes a different width later). This rule *replaces* the standard "MAIN RACK" — do **not** additionally draw the step-5 MAIN RACK.
       - **PB Case 2, CT Case 1:** Mirror of the above. Here PB is Case 2 (active side far from PB) and CT is Case 1 (active side close to CT), so the gap to bridge is on the PB side. Draw **one straight perpendicular line** on the MAIN RACK axis from the **PB center** to **CT's Case 1 rack buffer** (the overlapped CT side) — its far ("start") point lands on the CT rack buffer, and the line serves as the MAIN RACK. Because the bridging gap is on the PB side (which this line traverses), no separate CT connector is drawn. This *replaces* the step-5 MAIN RACK.
       - **Same case (PB & CT both Case 1, or both Case 2):** If the best halves for CT and PB are parallel and share the same x-range or y-range projection (overlapping), the standard A* connection (step 7) is skipped. Instead, extend the Power Block's MAIN RACK line directly to meet the Cooling Tower (CT) rack buffer line, connecting them in a single straight perpendicular line aligned with the Power Block's center.
2. **Jointly** select the PB and CT spine sides (once each block's active case from step 1 is fixed). Instead of choosing each side independently by "which side points toward RAW":
     - **Mutual-facing filter (primary).** Keep only `(PB side, CT side)` combinations where **both** sides face each other — i.e. CT's center lies on the outward side of the chosen PB side, and vice versa. A side facing *away* from the other block always forces a U-shaped wrap, so those pairs are excluded. (If no pair qualifies, fall back to all combinations.) Sides lying fully outside the plot are pruned first.
     - **Tie-break.** Among the surviving facing pairs, minimise `gap(PB side, CT side) + W_RAW · dist(PB side midpoint, RAW center)`, where **gap** is the L1 (Manhattan) distance between the two sides (perpendicular separation + any lateral offset where their projections don't overlap), picking the closest facing pair. `W_RAW` (`SPINE_RAW_WEIGHT`, default 0.25) is small — RAW only nudges the PB side (whose midpoint ranks the RAW/Demi candidates in B-2/B-3) when gaps tie.
     - The dependence on the PB↔CT relative position emerges naturally: a side-by-side PB/CT yields left/right facing sides, a stacked one yields top/bottom — always the sides that let the connection run straight out toward the other block rather than wrapping around.
3. Divide both selected full segments by their midpoints into two half-lines each.
4. Compare all 4 combinations of half-lines, take only the 2 closest half-lines to each other as the PB and CT rack segments, and prune the not selected halves.
5. Draw a perpendicular connection from the Power Block (PB) center to the perpendicular projection point on the selected PB segment, and call this line "MAIN RACK" (it will have separate logic later, except under the overlap exception above).
6. The selected closest half-lines, any constructed perpendicular lines become the **PB↔CT spine centerlines**.
7. Connect the PB and CT centerlines: if they do not overlap (the standard case), evaluate two connection strategies using A* routing and select the shorter one:
   - **Search 1**: An A* path between the PB spine (`best_pb_half`) and the CT spine (`best_ct_half`), where all block footprints (including the Power Block) are blocked as standard obstacles.
   - **Search 2**: An A* path between the full `MAIN RACK` (starting from the PB center point `(pb_cx, pb_cy)`) and the CT spine (`best_ct_half`), where the Power Block footprint is unblocked, allowing the connection to step on the PB footprint.
   Prune the unchosen path and snaps/simplifies the chosen path to form the single continuous spine network (enforcing road clearances and turn penalties for simple L-shapes).
   - **Same-case Overlap Exception**: If both blocks use the same case (both Case 1 or both Case 2), are parallel, and overlap, the standard A* routing is skipped. The connection is made by extending the Power Block's MAIN RACK line directly to connect the Power Block center to the Cooling Tower (CT) rack buffer line in a single straight perpendicular line aligned with the Power Block's center.
   - **[Polygon change] MAIN RACK vs the PB↔CT connection.** In polygon mode, the same-case overlap shortcuts are **skipped**:
     - The **MAIN RACK** is only the short stub from the **PB centre to the PB rack-buffer line**.
     - The **PB↔CT connection always uses the A\*** routing (Search 1, with **all blocks — including the Power Block — treated as obstacles**), so it **routes around blocks** like the Warehouse instead of cutting a U-shaped or straight line through them. (Search 2 is used as a fallback).
     - Legacy **rectangle** mode is unchanged (guarded by the polygon flag).
8. **Cut the MAIN RACK from the PB↔CT spine (case1 buffer split).** After the spine network is connected (step 7), intersect the **MAIN RACK** axis (PB center → active PB rack-buffer) with the Power Block's **Case 1 (6 m) rack buffer**. This crossing is the **cut point**.
     - **PB center → cut point** = **MAIN RACK OUTPUT** — the part of the spine that lies *inside* the PB's own 6 m rack zone (drawn/handled as the Power Block's own main rack).
     - **cut point → rest** = part of the **PB↔CT spine** (it joins `best_pb_half` and the step-7 A\* connection toward CT).
     - The cut only **adds a vertex** at the case1-buffer line — geometry and connectivity are unchanged, and the PB↔CT connection still uses the step-7 A\* routing. When the active PB case is already **Case 1**, the cut lands on the rack's far end (degenerate leftover) and the MAIN RACK OUTPUT equals the whole stub.

**B-2 — RAW Water candidate points**

1. Take RAW Water Tank's active rack-buffer rectangle — 4 corner points
2. Prune any corner outside the plot boundary.
   - **[Polygon change] Candidate pruning.** Rack-buffer candidate points that fall **outside the polygon** are dropped.
3. Measure distance from each remaining corner to the **center of PB's selected rack-buffer line** (from B-1).
4. Keep the **2 closest corners** as candidate RAW points.

**B-3 — Demi Water candidate points**

Same process as B-2, applied to Demi Water Tank → keep 2 candidate Demi points.
- **[Polygon change] Candidate pruning.** Rack-buffer candidate points that fall **outside the polygon** are dropped.

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

*WWT Split Rule:*
If the projection line (or closest connection line) between the WWT and the RAW/Demi candidates intersects the Power Block footprint, WWT is on the opposite side of the Power Block. WWT is disconnected from the RAW-Demi network.

**Result:** 
- If not split: 3 points — one each on RAW, Demi, WWT rack-buffer lines → tightest water triangle.
- If split: 2 points — one each on RAW and Demi rack-buffer lines → RAW-Demi network (WWT is split).

**B-5 — Water Cluster Spine**

Connect the 3 triangle points using **orthogonal A\* paths** (no diagonals, cell size = 2 m) with a **turn penalty of 10** so paths come out straight or single-L rather than zig-zagging.
- Paths may travel along any block's active rack-buffer line or through empty grid cells, but must run **on** a block's rack-buffer line rather than cutting the footprint→buffer gap (buffer-corridor rule above; footprint-only fallback if blocked).
- Cannot intersect any block footprint.
- Two shortest paths of the three possible pairings are kept; the longest pair is dropped.

#### §3.6.C Network Connection

**C-1 — Unify into one network (A* routing)**

Route the shortest orthogonal path from the **PB/CT spine network** (comprising the PB centerline, CT centerline, their connection segment, and the **main rack segment**) to the **water cluster spine** (restricted routing: only along existing spine lines and rack-buffer edges).

The connection must:
- Extend an existing spine line, OR route along another rack block's active rack-buffer line.
- Never cross any block footprint.
- Fallback: if restricted routing fails, open the grid fully and re-route.

**WWT Split Connection:**
If WWT was split:
- Route the RAW-Demi network to the PB/CT spine network (which automatically routes from Demi if it is closer).
- Route WWT's rack-buffer boundary separately to the PB/CT spine network via the shortest orthogonal path.

**C-2 — Flare Pipe Rack Connection**

1. If any existing rack segment already touches the Flare's active rack-buffer rectangle → connection satisfied.
2. Otherwise:
   - Route the shortest orthogonal path from the boundary (all 4 segments) of the Flare's active rack-buffer rectangle to the PB↔CT spine centerlines or their connection line from Step 7 (excluding any segments that touch the Power Block center).
   - The Flare connection uses the **geometric** (buffer-corridor) grid directly, *skipping* the extended-line restricted mode — the latter spans each spine/water segment across the whole site and can pull the link to a non-nearest point. This makes the Flare attach at the closest corner of its rack buffer.
   - **[Polygon change] Flare connects to the NEAREST rack.** The Flare attaches to the closest segment of the **whole rack network** (spine + water cluster + connectors, including the main rack at the PB centre) — not only the PB↔CT spine.
   - This single A* search automatically connects the closest points between the Flare's rack-buffer boundary and the target spine network.
   - Add this path to the unified network.

**C-3 — Cleanup**

After the full rack network is routed, trim redundant geometry.

1. **Power Block and Cooling Tower free ends.** The PB and CT spine halves (`best_pb_half` and `best_ct_half`) often stick out past the points where the network actually connects to them (e.g. the PB↔CT connector meets them partway along, leaving dangling stubs).
   - Find every **junction** on `best_pb_half` and `best_ct_half` — each point where another rack segment meets them.
   - **≥ 2 distinct junctions:** trim the half to span only between the outermost junctions, removing the free end(s) beyond them.
   - **< 2 junctions** (both ends free, or only a single touch): the half is redundant → **prune it entirely**, and also **prune any perpendicular connector** created to bridge to it (to avoid leaving dangling stubs like the 13m bridge segment).
2. **Stub segments.** Prune any rack segment shorter than **6 m** (`MIN_RACK_SEG_LEN`) — tiny leftover stubs from snapping/trimming.
3. **[Polygon change] Water-cluster free-end cleanup.** The water spine gets the same free-end trimming as the PB/CT spine, but **anchored to the water-triangle connection points** (on the RAW/Demi/WWT rack buffers): a trim is kept only if the network **still touches every water rack buffer** it touched before — otherwise it is reverted.

**Rack output:** Single connected rack polyline network (centerlines, 6 m wide). Becomes an obstacle for subsequent road placement.


### §3.7 Access Roads (Part 1 + Part 2 Perimeter Loop)

Each block that needs a road connection receives **two** independent access roads:
- **Part 1 (midpoint connection):** a direct route from the block's road-buffer midpoint to the nearest existing road network segment.
- **Part 2 (perimeter loop):** an independent route around the block's inflated bounding box, connecting to the road network at a **different** point from Part 1, forming a loop.

> [!IMPORTANT]
> **Gate spur restriction.** Access roads (Part 1 and Part 2) are **not allowed to connect to the gate spur**. They can only connect to the Power Block ring road or the ring spur.

**Connected blocks:** Cooling Tower, Admin Building, GIS, WT/WWT, Warehouse.

> [!NOTE]
> **Flare exclusion.** The Flare is excluded from this access road system — it receives only its 6 m plant-facing access road via Group B (§10.1.C).

**Footprint clearance (hard) vs road buffer (soft guide).** No access road — Part 1 or Part 2 — may ever be drawn on or right against a block footprint. Three layers enforce this:
- **Hard grid skirt (2 m):** the routing grid blocks every footprint cell plus a 2 m skirt (`mark_building(inflate_m=2.0)`), so A\* cannot route onto any cell within 2 m of a block. Combined with the graded buffer below, routes in practice stay well clear. The last-resort L-path (used only if A\* fails) prefers the leg that avoids footprints.
- **Graded road buffer (soft guide):** the buffer penalty is **graded** — 500 at the footprint, falling linearly to 0 at the buffer edge (8 m / 16 m). The buffer acts as a *guide*, not a wall — A\* is pushed away from footprints and naturally runs along the buffer edge line (where `P_buf` and the Part 2 rectangle `R` sit), instead of hugging the block at 1–2 cells as the old flat penalty allowed.
- **Geometric clearance (4 m):** the untracked Part 2 candidates (`build_candidate_path` / `fallback_connection`'s walk along `R`) **reject** any segment that crosses a block footprint + 4 m clearance (possible when a neighbouring block sits on this block's `R`, or a corner was clipped to the plot boundary); rejection falls through to A\* routing. The same 4 m clearance guards the arrival-straightening slides (§3.7.B step 7).

**Rack clearance (`RACK_ROAD_CLEAR` = 8 m).** Access roads may **cross** a rack (perpendicular), but must not run **parallel alongside** one within 8 m of its centerline. Enforced three ways:
- The A\* routing grid gets **direction-aware** flat penalty walls: horizontal moves are walled (~3000) in the 8 m band around *horizontal* racks, vertical moves around *vertical* racks — so crossing a rack band perpendicular costs nothing, while running along it forces A\* out to the 8 m line. Cells on the existing road network (and on newly added access roads) are zeroed so connecting along roads stays free.
- The traced Part 2 candidates and the `route_from_point` L-paths reject any segment that runs parallel to a rack within 8 m with > 2 m of side-by-side overlap (`segment_near_rack`), falling through to the rack-aware A\*.
- The arrival straightening (`straighten_arrival`) will not slide a leg into a parallel run alongside a rack.

**Geometry polish (Part 1 & Part 2).** After the arrival straightening, each road is polished before being added to the network:
- **Orthogonal only:** any diagonal segment is split into an L (`orthogonalize_path`) — the corner is chosen to continue the previous segment's axis, guarded against footprints and racks.
- **Minimal zigzag (L over Z):** a small perpendicular step (≤ 4 m) beside a long leg is collapsed (`collapse_jogs`) by sliding the neighbouring leg sideways onto the straight line. Path endpoints (the loop junction and the network connection) never move; every slide is footprint/rack-guarded.
- **No buffer-center stub:** if Part 1 leaves `P_buf` **perpendicular** to the block side (pointing away from the block) and then turns — at any stub length — that stub is not drawn — it would read as a dead spur aiming at the block's buffer center. The turn point becomes the **loop junction**: Part 1 starts there, and Part 2 is re-headed to start there too via an orthogonal connector (typically making Part 1 + Part 2 one straight line through the junction). **Two-point case:** when the *entire* Part 1 is that stub (two points — `P_buf` straight onto an existing road), Part 1 is dropped from the output completely, and the stub's network-end point is the loop junction where Part 2 starts.

#### §3.7.A Part 1 — Midpoint Connection

1. **Determine the closest side** of the block to the core road network (ring road + gate spur + ring spur), ignoring secondary access roads of other blocks.
2. **All opposite sides are valid:** Since access roads are allowed to ignore the plot boundary, no plot containment or minimum boundary margin checks are performed on the starting midpoints.
3. **Choose the starting side:** Choose the ideal opposite side to the closest core road side (e.g. the West side of WT/WWT).
4. **Compute P_buf** for the selected side.
5. **Route from P_buf** to the nearest road network cell using `route_from_point()`, which attempts:
   - An L-shaped (2-segment) path via horizontal-first or vertical-first routing, checking clearance against block road buffers.
   - If both L-paths are blocked, an **A\* search** with a turn penalty of 50 and a cell cost function that penalises cells inside block road buffers.
6. **Spur stripping:** The first point of the path (P_buf itself) is always stripped — the visible Part 1 road starts from the first network-facing point, not from the block's buffer edge.
7. **Post-processing:** Deduplicate adjacent points → simplify collinear segments → snap to the 2 m grid → post-snap dedup.

#### §3.7.B Part 2 — Perimeter Loop

Part 2 provides a **second, independent** approach to the block that forms a **loop** with Part 1. It traces the block's inflated bounding box `R` to find a connection point on the road network distinct from Part 1's connection.

1. **Construct the offset rectangle `R`:** the block footprint padded outward by `B_offset`, with corners V_se, V_ne, V_nw, V_sw.
2. **Directional sequences:** Define **CCW** and **CW** traversal orders starting at `P_buf` and visiting all 4 corners of `R`, depending on the opposite side (N/S/E/W).
3. **Trace each direction** with `build_candidate_path()`:
   - Walk along `R`'s edges from `P_buf` through each corner in sequence.
   - At each segment, check for **intersections** with the existing road network. The first intersection found (that is ≥ 15 m from Part 1's connection point) becomes the Part 2 terminus.
   - Corner points are **not clipped to the plot polygon** (clipping is disabled since access roads are allowed to ignore the plot boundary).
4. **Fallback connection:** If no intersection is found along `R`'s edges, `fallback_connection()` routes each corner of `R` to the road network via A\* and picks the shortest total path.
5. **No-Retrace / No-Hairpin check:** `check_overlap()` samples points along the Part 2 candidate path and measures their distance to the Part 1 centerline. If more than `epsilon` (5 m) of the path runs within `threshold` (12 m) of Part 1, the candidate is rejected (it would overlap/retrace Part 1). Both CCW and CW candidates are evaluated.
6. **Direction selection:**
   - If both CCW and CW pass the no-retrace check → pick the **shorter** one.
   - If only one passes → use that one.
   - If neither passes → fall back to the shorter candidate.
7. **Terminal alignment:** Part 2's last point is projected onto the nearest Part 1 road segment using `align_terminal_to_network()` to close any grid-snapping gap (only applied for gaps between 0.1 m and 16 m). Additionally, the **arrival of both Part 1 and Part 2 is straightened** (`straighten_arrival()`), so each road runs straight and turns only once, at the network. Two patterns are fixed:
   - *Stub:* a long leg running parallel to the target road line a few cells away, ending in a tiny stub (≤ `B_offset`) onto the connection point — the offset leg is slid onto the connection point's line (e.g. an approach to a ring road corner continues along the corner's axis instead of dog-legging next to it).
   - *Offset terminal:* the final leg runs parallel to a network road line (ring road edge, ring spur leg, an earlier access road, …) with its terminal ending a cell or two beside it (A\* cell rounding, no stub drawn) — the parallel target line is searched for **explicitly** (projecting to the single nearest network point misses this near corners, where the nearest segment is the perpendicular one) and the whole leg is slid sideways onto it. Capped at ≤ 2 grid cells sideways, so genuine connections to other roads are never rerouted.
   Part 1 aligns against the Part-1 network; Part 2 against the combined network plus its own block's Part 1. **Clearance guard:** a straighten slide is committed only if the resulting tail keeps ≥ 4 m from every block footprint — footprint clearance outranks the single-turn cosmetic, so a slide that would push the road against a block is skipped and the orthogonal stub is kept instead. The terminal-alignment projection (above) likewise inserts an orthogonal corner rather than dragging the endpoint perpendicular to its leg (which would produce a diagonal segment).
8. **Start alignment (loop closure):** Part 1 and Part 2 must share their start point `P_buf` and pass through it as **one straight line**. Two sub-steps:
   - *Restore the shared vertex:* the Part 1 spur strip (§3.7.A step 4) removes `P_buf` from Part 1's visible path — invisible in the normal case (Part 1 resumes right at `P_buf`'s grid cell), but when Part 1's first hop heads *away* from the block (e.g. hugging a slanted plot edge), the loop is detached. `P_buf` (snapped, = Part 2's first point) is then restored as Part 1's first point (gaps 0.1–16 m, mirroring step 7).
   - *Straighten the departure:* A\* can hug the *outside* of the block buffer, leaving Part 1 running on a small parallel offset next to Part 2's line (a jog through the shared point). Part 1's initial points that deviate ≤ `B_offset` from the line of Part 2's first segment are collapsed onto that line, so Part 1 continues Part 2's first segment straight in the opposite direction. If this moves Part 1's terminal, the terminal is re-projected onto the road network (same rule as step 7).

#### §3.7.C Forbidden Zone

Blocks whose footprint overlaps the **forbidden zone** (checked with a 5 m tolerance) are completely excluded from having any access roads generated (neither Part 1 nor Part 2). The forbidden zone is defined as the bounding box between the boom barrier (using the start and end points) and the ring road, choosing the boundary coordinates farthest from the boom midpoint. Its purpose is to prevent access roads from drawing in or near the congested gate area.

#### §3.7.D Road Network Growth

After each block's Part 1 and Part 2 are generated, they are **added to the road network** (`road_segments` + `road_cells`) so that subsequent blocks can connect to them. The road cell penalty grid is also updated (cells on existing roads get penalty 0), enabling A\* routing to prefer connecting to nearby roads over long detours.

- **Part 1 segments** are added to both the Part-1-only network (`road_segments_p1`) and the combined network (`road_segments_all`).
- **Part 2 segments** are added only to the combined network (`road_segments_all`), so later blocks can connect to Part 2 roads but Part 1 routing remains stable.

#### §3.7.E Part 3 — Boundary Trim (cleanup)

Access roads are routed **ignoring the plot boundary** (A\* may excurse past a slanted edge, e.g. a Part 2 loop around a block near the top edge). A final cleanup pass (Stage01 Step 11.5) trims every access-road centerline at the **temporary (inset) plot boundary**:

- **Depth-based clipping**, not edge-crossing based: a road can run parallel to an edge slightly outside it and continue past a corner without ever crossing an edge line. Each segment is sampled ~every 1 m; runs where the signed depth to the boundary is ≥ −`EDGE_TOL` (0.3 m, tolerance for grid-snapped roads sitting on the line) are kept, and cut points are linearly interpolated onto the boundary.
- A road that crosses out and back in **splits into separate pieces** (same block/part labels); each piece is deduplicated and collinear-simplified.
- Pieces shorter than **4 m** are discarded.

This runs after all Part 1/Part 2 generation and network growth, immediately before the output step.

> [!NOTE]
> The old perimeter fire road approach (grid-based boolean union of buffers + morphological closing + contour tracing) has been **fully replaced** by this Part 1 + Part 2 system. The old §3.7 contour-tracing algorithm is no longer used.




### §3.8 Recenter

> [!IMPORTANT]
> **Runs pre-roads (Stage01 Step 10.9), not as the final step.** Recenter now happens **before** the §3.7 access roads are generated, so roads are placed around the already-centered layout and connect to the recentered gate spur — they never need recentering afterward. Consequently the content bounding box is computed over the **non-road** geometry only (blocks + racks + ring road + ring spur + gate spur + boom); access roads do not exist yet and are excluded. Enabled via `PRE_RECENTER_ENABLED = True`; the old final-step recenter (Step 12) is now just a pass-through that emits the already-recentered plot/gate/spur/death-zone.

The placed layout is usually off-center inside the plot. Recenter fixes this **without moving any content** — instead it slides the **plot polygon** (and the gate point, which belongs to the plot) so the plot's center lands on the content's bounding-box center.

**[Polygon change]** Recenter slides the **plot polygon (all corners)** by the same amount, rather than just shifting a bounding box, while preserving the content coordinates.

1. Compute the **content bounding box** over the **non-road** placed geometry —
   block footprints + ring road + ring spur + gate spur + boom barrier + all
   rack/water segments. (Access roads are excluded — they are generated *after*
   this step.)
2. `content_center = ((min_x+max_x)/2, (min_y+max_y)/2)`.
3. `delta = content_center − plot_center`, where `plot_center` is the polygon's
   **area centroid** (`Plot.centroid`), *not* its bounding-box center — with
   slanted edges the polygon's mass sits away from the bbox middle, and
   centering on the bbox systematically biases the layout toward the cut-off
   side. (Rectangle fallback: centroid == bbox center == `(sw/2, sl/2)`.)
   **Containment clamp [Polygon change]:** with a rectangle, centering the plot
   on the content bbox always keeps the content inside; with slanted polygon
   edges the move can push boundary-hugging content (e.g. an access road along
   a slanted edge) outside. `delta` is therefore scaled down (binary search) to
   the largest fraction such that **each content point individually** stays at
   least as deep inside the polygon as it started (0.5 m slack for grid-snapped
   points sitting right on the boundary). Per-point, not global — one point
   already poking past the boundary must not license every other point to sink
   that far too. The gate spur's final L to the gate is **excluded** from the
   clamp: its points sit on the boundary by definition and the leg is rebuilt
   after the move (step 6).
   **Per-axis clamping:** the x and y components of `delta` are clamped
   **independently** (then the combined vector is re-verified once, since
   slanted edges respond to diagonal moves). A pinch in y — e.g. a block
   sitting on the bottom edge — must not also cut the x slide, and vice
   versa; a single shared scale factor would couple them.
   **Damping (`RECENTER_DAMPING` = 0.5):** only half of the clamped delta is
   applied. The full clamped slide always parks the pinned content (e.g. a
   CAD-anchored block drawn near the boundary) exactly ON the temporary
   boundary — squeezing one side to zero margin; halving splits the remaining
   margin between both sides instead.
4. **Move the plot:** new plot polygon corners are shifted by the (clamped, damped) `delta` (translating the whole polygon shape), moving its center toward `content_center`. Output as `plot_bounds` (the shifted polygon's bounding box `= (minx, miny, width, height)`) and `plot_polygon` (shifted corners).
5. **Move the gate point perpendicular to its edge only** — N/S gate shifts by
   `delta_y`, E/W gate shifts by `delta_x`. This keeps the gate on the moved
   boundary line without sliding *along* the edge (which would stretch the exit
   road sideways and detach it from the gate house / its spur).
6. **Extend the exit line to the recentered gate.** The gate spur's boom crossing
   (`exit_helper → bb_mid → other_corner`) stays put; only its final L to the
   gate is rebuilt so the gate spur reaches the recentered gate.
7. **Recompute the gate death zone** as the rectangle between the fixed `bb_mid`
   and the recentered gate.
8. **All other content keeps its original coordinates** (blocks, racks, ring
   road, ring spur, buffers, pb_center — unchanged). Only `plot_bounds`,
   `plot_polygon`, `gate_point`, the gate spur's exit-line leg, and the death zone move.

The pre-recenter plot and gate are also output (`plot_bounds_before`,
`gate_point_before`) and can be drawn as a faded overlay in the dashboard via the
"§3.8 — Plot + gate before recenter" toggle (default off).

## §4. Step 1 Output Dictionary

```python
{
    "blocks":                list[dict],   # name, x, y, width, height, color, rotated
    "boom_barrier":          list[tuple],  # 16m line from Gate House inner edge
    "ring_road":             list[tuple],  # PB ring road closed polyline
    "gate_spur":             list[tuple],  # gate → ring road polyline
    "ring_spur":             list[tuple],  # ring road → gate spur polyline
    "access_roads":          list[list],   # per-block access road polylines (Part 1 + Part 2)
    "access_roads_blocks":   list[str],    # block name for each access road
    "access_roads_parts":    list[str],    # "part1" or "part2" for each access road
    "rack_buffers":          dict,         # {block_name: {offset_key: rect}}
    "rack_segments":         list[seg],    # unified rack network centerlines
    "rack_candidates":       list[tuple],  # RAW/Demi candidate corner points
    "active_rack_cases":     dict,         # {block_name: "case1_rack"|"case2_rack"}
    "water_triangle":        list[tuple],  # 3 points: RAW, Demi, WWT on rack buffers
    "gate_point":            tuple,        # (x, y) gate midpoint, recentered (§3.8)
    "gate_point_before":     tuple,        # (x, y) gate before recenter (§3.8; debug overlay)
    "plot_polygon":          list[tuple],  # [Polygon change] TEMPORARY (5 m inset) plot corners, after recenter
    "plot_polygon_original": list[tuple],  # REAL CAD plot corners, after recenter (main drawn boundary)
    "plot_polygon_before":   list[tuple],  # temporary (inset) plot before recenter (debug)
    "plot_polygon_original_before": list[tuple],  # REAL CAD plot before recenter ("before recenter" overlay)
    "plot_bounds":           tuple,        # (x0, y0, sw, sl) plot rect, recentered (§3.8)
    "plot_bounds_before":    tuple,        # (0, 0, sw, sl) plot before recenter (§3.8; debug overlay)
    "recenter_delta":        tuple,        # (dx, dy) plot/gate shift (§3.8)
    "gate_death_zone":       tuple|None,   # (x, y, w, h) or None
    "pb_center":             tuple,        # (pb_cx, pb_cy)
    "cell_size":             int,          # 2
    "boundary_tol_used":     float,        # boundary tolerance used for this layout
    "boundary_pass_label":   str,          # human-readable pass label
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

## §6. Key Differences from Phase 05

| Aspect              | Phase 05                              | Stage 1                                           |
|---------------------|---------------------------------------|---------------------------------------------------|
| Coordinate system   | Continuous float (metres)             | Snapped to 2m grid                                |
| Road creation       | A* from gate to each building entrance| Blocks placed first; road network built around block buffers |
| Building entrances  | Required for routing                  | Not used in Step 1; deferred to Step 2            |
| Ring Road           | Hand-injected geometry segment        | Native graph edge, merges where overlapping       |
| Road classification | Single type                           | Primary (fire) / Secondary (stubs) / Access (S2) |
| Block buffers       | Fixed 15m all sides                   | 8m default; 14m on rack sides                     |
| Perimeter road shape| Rectangle only                        | Polygon — 4–6+ sides, generated from buffers      |
| Perimeter setback   | Hard-coded                            | `PERIMETER_SETBACK` configurable constant         |

## §7. Constants Quick Reference

```python
CELL_SIZE          = 2    # metres per grid cell
ROAD_BUFFER        = 8    # road CL from non-rack block edge
BLOCK_BUFFER       = 16   # min block-to-block gap (no rack)
BOUNDARY_TOLERANCE = 10   # relaxed bound for tight fits
PB_RING_OFFSET     = 16   # PB ring road CL from PB face (engine value; plan text said 14)
PERIMETER_SETBACK  = 5    # perimeter road outer edge from boundary
PERIMETER_ROAD_W   = 8    # perimeter road width
PERIMETER_CL_DIST  = 9    # = SETBACK + ROAD_W / 2

RACK_WIDTH         = 6    # pipe rack width
ROAD_W_RACK_OFFSET = 14   # road CL on a rack side
B2B_W_RACK_OFFSET  = 28   # block-to-block on a rack side
RACK_CASE1_OFFSET  = 6    # rack CL: Case 1 (block → rack → road)
RACK_CASE2_OFFSET  = 22   # rack CL: Case 2 (block → road → rack)
```

> The values above are quoted from the original Stage 1 plan. The live engine
> (`Core/Stage01.py`) is the runtime authority — where it differs (e.g.
> `PB_RING_OFFSET = 16`, `ROAD_W_RACK_OFFSET = 16`, `B2B_W_RACK_OFFSET = 30`,
> `RACK_CASE1_OFFSET = 8`, `RACK_CASE2_OFFSET = 24`), the engine value wins.

## §10. References

Reference material (not procedural steps).

### §10.1 Road Access by Block

#### §10.1.A Special Cases

| Block       | Road   | Access Points                  | Notes                            |
|-------------|--------|--------------------------------|----------------------------------|
| Gate House  | 8m     | 1 — the gate itself            | Gate IS the access point         |
| Power Block | 8m     | 4 corners of PB Ring Road      | Ring road serves as access       |

#### §10.1.B Group A — 8m Road Connections

| #  | Block         | Count | Corner Selection Rule                                               |
|----|---------------|-------|---------------------------------------------------------------------|
| 2  | GIS           | 2     | Corner near boundary + corner near PB (diagonal opposite)          |
| 3  | RAW Water     | 1     | Boundary corner **furthest from Demi Water Tank**                  |
| 5  | Cooling Tower | 2     | Corner near boundary + corner near PB (diagonal opposite)          |
| 6  | WT/WWT        | 1     | Corner nearest to plot boundary                                     |
| 7  | Warehouse     | 2     | Corner near boundary + corner near PB (diagonal opposite)          |
| 9  | Admin         | 1     | Corner nearest to Gate House                                        |

**Total:** 9 × 8m connections across 6 blocks.

#### §10.1.C Group B — 6m Road Connections

6m roads represent lower-traffic secondary access (rack corridors, chemical delivery, maintenance).

| #  | Block         | Count | Access Point Position                             | Notes                                    |
|----|---------------|-------|---------------------------------------------------|------------------------------------------|
| 3  | RAW Water     | 1     | Corner near WT/WWT                                | Chemical/maintenance delivery            |
| 6  | WT/WWT        | 1     | Corner near RAW Water                             | Truck-heavy chemical delivery on 8m side |
| 8  | Flare         | 1     | Corner on plant-facing side only                  | NEVER boundary/leeward (radiation)       |
| 9  | Admin         | 1     | Corner opposite to Gate                           |                                          |
| 10 | Demi Water    | 1     | Corner near pump skid (PB-facing)                 | Low-traffic, single access               |

**Total:** 5 × 6m connections across 5 blocks.

#### §10.1.D Complete Access Summary

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

# PART III — RULE ENGINE REFERENCE

> The scoring engine currently lives in [`_Archive/Legacy_Pipeline_P05/`](_Archive/Legacy_Pipeline_P05/)
> (`rules.py`) and is **to be re-integrated** with the Stage01 output in a later
> step. Kept here as the rule SSoT. Layouts are scored by a **Total Penalty Score**
> (lower = better; 0 = perfect).
>
> **[Polygon change]** Rules that measure **distance to the boundary** now measure the distance to the **nearest real side of the polygon** (including diagonals), rather than a simple bounding box edge.

## Available Rule Types

| Rule Type             | Function in `rules.py`        | What it checks                                        | Penalty Mode |
| :-------------------- | :---------------------------- | :---------------------------------------------------- | :----------- |
| `center_proximity`    | `_eval_center_proximity()`    | Distance from building center to plot center          | Linear       |
| `boundary_setback`    | `_eval_boundary_setback()`    | Min distance from any edge to site boundary           | Flat         |
| `windward_edge`       | `_eval_windward_edge()`       | Is building on the windward side of the plot?         | Flat         |
| `min_distance`        | `_eval_min_distance()`        | Center-to-center distance must be ≥ threshold         | Linear       |
| `max_distance`        | `_eval_max_distance()`        | Center-to-center distance must be ≤ threshold         | Linear       |
| `leeward_edge`        | `_eval_leeward_edge()`        | Is building on the downwind (leeward) side?           | Flat         |
| `rack_length`         | `_eval_rack_length()`         | Edge-to-edge distance between two connected buildings | Linear       |
| `pipe_rack_proximity` | `_eval_pipe_rack_proximity()` | Distance from building edge to nearest rack line      | Linear       |
| `road_proximity`      | `_eval_road_proximity()`      | Distance from building/rack to nearest road           | Linear       |
| `boundary_overflow`   | `_eval_boundary_overflow()`   | Penalty for buildings exceeding site boundaries       | Logarithmic  |

**Penalty Modes:** Linear = `excess × rate`; Flat = one-shot; Logarithmic = overflow.

## Phase 03 — The Three Giants (6 rules)

| ID | Group | Rule Type | Target | Threshold | Penalty | Condition |
|----|-------|-----------|--------|-----------|---------|-----------|
| PB-01 | Power Block | center_proximity | Plot Center | 20 m | 100 / m | Excess beyond 20 m |
| PB-02 | Power Block | boundary_setback | Primary Road | 5 m | 5000 flat | If any edge < 5 m |
| CT-01 | Cooling Tower | leeward_edge | Wind | 120 m | 1000 flat | Must be downwind |
| CT-02 | Cooling Tower | min_distance | Admin | 50 m | 500 / m | If distance < 50 m |
| AD-01 | Admin | boundary_setback | Primary Road | 20 m | 1000 flat | If any edge < 20 m |
| AD-02 | Admin | max_gate_distance | Site Gate | 80 m | 100 / m | If distance > 80 m |
| AD-03 | Admin | windward_edge | Wind | 30 m | 1000 flat | Must be upwind |

## Phase 04 & 05 — Expanded rules (rectangles)

| ID | Group | Rule Type | Target | Threshold | Penalty | Condition |
|----|-------|-----------|--------|-----------|---------|-----------|
| GH-01 | Gate House | boundary_setback | Primary Road | 0 m | 5000 flat | Must be on site boundary |
| GIS-01 | GIS | boundary_setback | Primary Road | 15 m | 1000 flat | Setback from boundary |
| WH-01 | Warehouse | boundary_setback | Primary Road | 15 m | 1000 flat | Setback from boundary |
| WH-02 | Warehouse | max_distance | Power Block | 250 m | 100 / m | Compact layout |
| FL-01 | Flare | leeward_edge | Wind | 30 m | 1000 flat | Must be downwind |
| FL-02 | Flare | min_distance | Admin | 100 m | 500 / m | Safe distance from Admin |
| FL-03 | Flare | min_distance | Power Block | 50 m | 300 / m | Safe distance from PB |
| FL-04 | Flare | max_distance | Power Block | 150 m | 100 / m | Compact layout |
| WW-01 | WT/WWT | boundary_setback | Primary Road | 10 m | 1000 flat | Setback from boundary |
| WW-02 | WT/WWT | leeward_edge | Wind | 50 m | 500 flat | Must be downwind |
| WW-03 | WT/WWT | max_distance | Power Block | 200 m | 100 / m | Compact layout |
| WA-01 | RAW Water | boundary_setback | Primary Road | 10 m | 1000 flat | Setback from boundary |
| WA-02 | RAW Water | min_distance | WT/WWT | 10 m | 200 / m | Near water treatment |
| WA-03 | RAW Water | max_distance | WT/WWT | 80 m | 100 / m | Not too far from WWT |
| CT-04 | Cooling Tower | max_distance | Power Block | 180 m | 100 / m | Compact layout |
| AD-04 | Admin | max_distance | Power Block | 150 m | 100 / m | Compact layout |
| DW-02 | Demi Water | max_distance | RAW Water | 40 m | 100 / m | Near RAW Water |

## Infrastructure (Road) rules

| ID | Group | Rule Type | Target | Threshold | Penalty | Condition |
|----|-------|-----------|--------|-----------|---------|-----------|
| RD-01 | Power Block | road_proximity | Perimeter Road | 3 m | 500 / m | Gap building↔road |
| RD-02 | Cooling Tower | road_proximity | Perimeter Road | 3 m | 500 / m | Gap building↔road |
| RD-03 | Admin | road_proximity | Perimeter Road | 3 m | 500 / m | Gap building↔road |

## Rack length rules (shorter = better)

| ID | Rack | A | B | Penalty |
|----|------|---|---|---------|
| PR-01 | Pipe Rack | Power Block | Cooling Tower | 50 / m |
| PR-03 | Pipe Rack | Power Block | WT/WWT | 30 / m |
| UR-01 | Pipe Rack | WT/WWT | RAW Water | 40 / m |
| UR-02 | Pipe Rack | WT/WWT | Cooling Tower | 30 / m |
| CT-03 | Cable Tunnel | GIS | Power Block | 20 / m (separate logic) |

**Connection map:** single 6 m Pipe Rack connects PB↔CT, PB↔WT/WWT, WT/WWT↔RAW,
WT/WWT↔CT, RAW↔Demi. Cable Tunnel (GIS↔PB) is *not* a rack. Admin gets no rack.

**Infrastructure constraints:** primary road 8 m · secondary/access 6 m · perimeter
fire road 5 m setback · road-to-building ≥3 m · road-to-rack ≥2 m · rack-to-block
≥2.5 m · pipe rack 6 m.

> **To add a rule:** add a row to the relevant table here, then add a matching dict
> to the `RULES` list in `rules.py`.

---

# PART IV — CODE & ROADMAP

## §A. UX Specification (Streamlit dashboard)

**Sidebar inputs:** site W/L sliders (100–1000 m), wind direction (4-way), gate
edge + ratio, fixed-anchor fine-tuning (Gate House / GIS / RAW Water), display
toggles (2 m grid, buffer guides, raw vs cleaned roads), random-seed control
(`Fix seed`).

**Main canvas:** Matplotlib 2D plan — rectangles for buildings, circles for RAW /
Demi / Flare with safety radii. Road colors: Ring Road / Spurs = pink, cleaned
internal = light green, perimeter loop = purple, pipe racks = orange.

**Status banner:** 🟢 Pass 1 (≥18 m margin) · 🔵 Pass 2 (inside, tight) · 🟡 Pass 3
(slight boundary overrun) · 🔴 failure (with debug guidance).

**Data tables:** Block Stats (x/y/size), Kept Paths (route lengths), Placement
Debug (per-stage failure counts when placement fails).

**User flow:** upload site CAD (DWG/DXF) + params → Step 1 (100+ layouts) → pick 3
favorites → Step 2 (detail/subdivide + score) → Step 3 (rank) → export DXF.

## §B. Code Architecture

### Current (working) layout

```
Core/
  Plot.py        # [Polygon change] new plot-shape helper
  CADImport.py  # [Polygon change] new CAD DXF importer
  Stage01.py      # the Stage 1 engine — generate_sketch() → plain dict
  Grid.py        # 2 m occupancy grid (obstacle marking, passability)
  Pathfind.py    # A* routing (turn penalty, width-aware)
  Groups.py      # block footprints, SHAPES, colors, dimensions
Dashboard/
  WebDashboard01.py   # Streamlit entry point (the working dashboard)
Data/            # Plot plan requirement.xlsx (source requirements)
tests/
  Test_Plot.py   # [Polygon change] new automatic checks
```

Dependency: `WebDashboard01.py → Stage01.py → Grid.py, Pathfind.py` (+ `Groups.py`, `Plot.py`, `CADImport.py`).

### Recommended future module split (professionalisation path)

`Stage01.py` is ~2.5k lines. For Streamlit scaling and a future C#/PyRevit port,
split it along these seams (engine stays UI-free; only `engine.generate_sketch()`
is public and returns a plain data dict that any front-end consumes):

```
Core/
  constants.py   # all offsets, buffers, tolerances in one table
  geometry.py    # footprint/corner/distance/overlap helpers
  placement.py   # block placement, magnet/snap, PB ring
  racks.py       # pipe-rack spines, BFS unification, Flare connection
  roads.py       # perimeter union/contour/simplify, spurs
  engine.py      # generate_sketch() orchestrator → dict
```

This is a **future** step, intentionally deferred. The current cleanup only
de-duplicated dead/identical helpers in place without changing behavior.

## §C. Roadmap (2026 H2)

- **Jun** — Streamlit + engine prototype; 12-block / 2 m-snap stability; DXF I/O test.
- **Jul** — Step 1 mass generation (100+ layouts) + 3-pick comparison UI.
- **Aug** — Step 2 large-block subdivision (e.g. PB → turbine/control/HRSG).
- **Sep** — Step 2 remaining small blocks + entrance stub roads + local rack opt.
- **Oct** — Step 3 ranking + comprehensive penalty-score report automation.
- **Nov** — CAD I/O hardening (exclusion zones, labels, dimensions, AutoCAD fit).
- **Dec** — reference-drawing validation, performance/render optimisation, release.

# PowerPlan AI — Layout_Gen_Design (Polygon Plot edition)

> **What this file is.** This is [`PROJECT.md`](PROJECT.md) updated for the **new
> plot shape**. Before, the plot was always a **rectangle**. Now the plot can be
> **any shape with up to 6 straight sides, including diagonal (slanted) sides**.
>
> - Parts that **changed** for the new shape are marked **[Polygon change]**.
> - The step-by-step work plan is in [`PLAN_Polygon_Migration.md`](PLAN_Polygon_Migration.md).
> - The original rectangle version stays in [`PROJECT.md`](PROJECT.md).

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

- Automate **Plot Plans** for power plants: place 60+ buildings on a site using
  engineering rules.
- Aim for a **compact layout**, even on narrow sites, with some flexibility to go
  slightly past the boundary when needed.
- Every result is meant to be **checked against real reference drawings**.
- **[Polygon change]** Sites can now be **real-shaped plots with diagonal sides**,
  not only rectangles.

**Tech used:** Obsidian (notes) · VS Code (code) · **Python** · **Matplotlib**
(drawing) · **Streamlit** (dashboard) · **ezdxf** (reading CAD files).

## 2. Status & Roadmap

| Phase | Title | Status |
|-------|-------|--------|
| 01 | The Empty Plot | ✅ |
| 02 | The Three Giants (PB, CT, Admin) | ✅ |
| 03 | Engineering Rules (scoring) | ✅ |
| 04 | 12 groups, rule engine | ✅ |
| 05 | Routing & sequential placement | ✅ |
| **06** | Grid-first generative layout | 🔄 |
| **P** | **Polygon plot migration** | 🔄 Phase 0 done — see the PLAN |

- Engine: [`Core/Step01.py`](Core/Step01.py)
- Dashboard: [`Dashboard/Road_Test.py`](Dashboard/Road_Test.py)

## 3. Methodology

- **Grid-first** — every block, road and rack snaps to a **2 m grid**. This keeps
  the math simple and fast.
- **Infrastructure-first** — roads and racks are placed **first**, then buildings
  go around them. Racks are more important than roads.
- **3-pass boundary tolerance** — if the site is tight, the program **tries 3
  times**, each time allowing a bit more room:
  - **Pass 1 (strict):** stay at least **18 m** inside every side.
  - **Pass 2 (normal):** stay fully **inside** the plot.
  - **Pass 3 (tight):** allow some blocks to go **up to 10 m past** a side.
  - **[Polygon change]** This "inside / outside" check is now done against the
    **polygon** (including diagonal sides), not the rectangle.
- **Multi-stage refinement** — Step 1 makes many rough layouts, Step 2 adds
  detail, Step 3 ranks them, Step 4 exports. Each step shows an **image + a
  score**.

---

# PART II — HOW STEP 1 WORKS

## §0. The 4 steps

- **Step 1 (Generate):** make 100+ rough layouts of the big blocks → you pick 3.
- **Step 2 (Detailing):** add small blocks and split big blocks into buildings →
  pick 3.
- **Step 3 (Variation):** make small changes to your chosen layouts → pick 1–3.
- **Step 4 (Export):** check all rules and save as a **CAD drawing (DXF)**.

**Rule:** roads come **before** buildings; racks come **before** roads.

## §1. The blocks

| #  | Block            | Notes                  |
|----|------------------|------------------------|
| 1  | Power Block      | central anchor — first |
| 2  | GIS              | near NE boundary       |
| 3  | Cooling Tower    | leeward (downwind)     |
| 4  | Flare            | leeward corner         |
| 5  | WT/WWT           | downwind               |
| 6  | RAW Water Tank   | near water tie-in      |
| 7  | Demi Water Tank  | near RAW Water         |
| 8  | Admin Building   | near Gate              |
| 9  | Gate House       | fixed on boundary      |
| 10 | Warehouse        | near boundary road     |

**Sizes (width × height, metres):** Power Block 150×150 · Cooling Tower 40×183 ·
Admin 30×25 · Gate House 12×12 · GIS 110×51 · Flare 40×40 · WT/WWT 81×56 ·
Warehouse 59×40 · RAW Water Tank 37×37 · Demi Water Tank 25×12. Non-square blocks
can be **turned 90°**.

## §2. The grid (sizes)

| Setting | Value | Meaning |
|---------|-------|---------|
| `CELL_SIZE` | 2 m | one grid square |
| `ROAD_BUFFER` | 8 m | block edge → road centerline |
| `BLOCK_BUFFER` | 16 m | gap between two blocks (no rack) |
| `BOUNDARY_TOLERANCE` | 10 m | how far a block may go past the boundary |
| `PB_RING_OFFSET` | 16 m | ring road distance from the Power Block |
| `PERIMETER_SETBACK` | 5 m | fire road edge from the boundary |
| `PERIMETER_ROAD_W` | 8 m | fire road width |
| `PERIMETER_CL_DIST` | 9 m | fire road centerline from the boundary |

- **[Polygon change]** The grid covers the **box around the polygon**. Grid
  squares that fall **outside the polygon** are blocked, so roads and racks
  **cannot cross a diagonal cut-off corner**.

## §3. Placing everything (the order)

```
1.  Fixed buildings   →  Gate House, GIS, RAW Water Tank   [from the drawing]
2.  Power Block       →  plot center ± wind jitter
3.  PB Ring Road      →  drawn around the Power Block
4.  Gate + Ring road  →  built from the boom + gate         [from the drawing]
5.  Boom Barrier      →  read from the drawing              [from the drawing]
6.  Floating blocks   →  Cooling Tower, WT/WWT, Warehouse, Flare, Admin, Demi
7.  Pipe Rack         →  6 m rack network
8.  Block buffers     →  safety rectangles around blocks
9.  Perimeter road    →  fire road around everything        [follows the polygon]
10. Access roads      →  small 8 m roads
11. Cleanup           →  tidy overlapping road lines
12. Re-center         →  slide the plot to center the layout [moves the polygon]
```

### §3.2 Fixed buildings — **[Polygon change]**

- Gate House, GIS, and RAW Water Tank are **read from the drawing** as real
  positions. There are **no more sliders** for them.
- They are snapped to the grid and checked to be **inside the plot**.

### §3.2.1 How much each block MOVES per generation (jitter rules)

Every time you press **Generate Layouts**, some blocks shift a little so you get
different options. This table is the **single source of truth** for that movement:

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
> **Why Gate House and boom are fixed.** The boom barrier is drawn touching the
> gate house. If the gate house jittered, the boom would float away from it. So
> the gate house (and its boom) are kept fixed; only RAW Water Tank still jitters
> among the CAD anchors.

### §3.3 Power Block

- Placed near the **plot center**, with a small random shift that depends on the
  **wind direction** (push it toward the windward side, leaving the leeward side
  free for the Cooling Tower and Flare).
- How far it may shift is a **percentage of the plot size**:
  - windward side: up to **35%** of width
  - leeward side: up to **5%** of width
  - sideways: up to **20%** of length
- It is 150 × 150 m (square), so turning it does not matter.
- **[Polygon change]** "Plot center" now means the **polygon center**, and the
  "inside the plot" check uses the polygon.

### §3.4 PB Ring Road, Gate Road, Boom — **[Polygon change]**

- **Ring Road:** a closed road **16 m** around the Power Block.
- **Boom Barrier:** **read from the drawing** (before, it was calculated).
- **Gate Road (gate spur):** uses the **original gate-spur logic** (kept as-is),
  so it **crosses the boom at 90°** at the boom midpoint and routes to the gate via
  `exit_helper → boom → other_corner → gate`.
  - **[Polygon change]** the boom side (N/S/E/W) and midpoint are taken from the
    **CAD boom line**, so the road crosses the boom exactly where it is drawn.
- **Ring Spur:** connects the **ring road** to the gate road (at `exit_helper`).
  It starts at the ring-road corner closest to `exit_helper` and avoids a U-turn.

> [!IMPORTANT]
> **Ring-spur connection rule.** When `exit_helper` falls **within** the ring
> road's x/y span → a clean straight projection drops onto the nearest ring edge
> (original behaviour). When `exit_helper` is **outside** the span → the ring spur
> routes an **L from the closest ring corner** with a **perpendicular final
> approach**, which guarantees it connects to the ring road (instead of landing
> just off it).

- **Gate Death Zone:** the area between the boom and the gate. Blocks stay out of
  it, and the fire road does not detour into it.

### §3.5 Floating blocks

- These blocks **stick to** blocks already placed, at the correct gap.
- The program tries **both rotations** and picks a spot near the target.
- **Boundary check — [Polygon change]:** the block's **safety rectangle** (its
  road buffer) must stay **inside the polygon**. If it would cross a side
  (including a diagonal one), the spot is rejected.
- **Gaps between blocks:**
  - rack block ↔ rack block: **32 m**
  - normal ↔ normal: **16 m**
  - mixed: **24 m**
- **Order and zones:**

  | # | Block | Stick near | Zone |
  |---|-------|-----------|------|
  | 1 | Cooling Tower | Power Block | leeward |
  | 2 | Flare | leeward **corner of the polygon** | leeward |
  | 3 | WT/WWT | Power Block | near RAW |
  | 4 | Warehouse | Power Block | — |
  | 5 | Admin | between Gate House & Power Block | middle |
  | 6 | Demi Water | RAW Water Tank | near RAW |

- **[Polygon change] Flare:** it is placed at the **leeward corner of the
  polygon** (before it was one of the 4 rectangle corners).
- **[Polygon change] Leeward zone:** "leeward half" is now the half of the plot on
  the downwind side of the **plot center**:
  - wind from East → leeward is the **left** half
  - wind from West → leeward is the **right** half
  - wind from North → leeward is the **bottom** half
  - wind from South → leeward is the **top** half

### §3.6 Pipe Rack (short version)

- One rack type, **6 m wide**, connects 6 blocks: Power Block, Cooling Tower,
  WT/WWT, RAW Water Tank, Demi Water Tank, and Flare.
- The rack is built as a **spine** between the Power Block and Cooling Tower, then
  the water tanks join, then the Flare joins with one short branch.

- **[Polygon change] Racks stay inside the plot.** Every rack routing grid now
  blocks all cells **outside the polygon** (`_mask_grid_to_plot`), so a rack can
  **never cross a diagonal/cut corner**. (The grids are re-masked after each reset
  inside `mark_b1_grids`, since the reset wiped the mask.)

- **[Polygon change] MAIN RACK vs the PB↔CT connection.** In polygon mode the
  special "overlap" short-cuts are **skipped**:
  - the **MAIN RACK** is only the short stub from the **PB centre to the PB
    rack-buffer line**;
  - the **PB↔CT connection always uses the A\*** routing (Search 1, with **all
    blocks — including the Power Block — treated as obstacles**), so it **routes
    around blocks** like the Warehouse instead of cutting a straight line through
    them. (Search 2, the through-PB short-cut, is only a fallback.)
  - Legacy **rectangle** mode is unchanged (these are guarded by the polygon flag).

- **[Polygon change] Flare connects to the NEAREST rack.** The Flare attaches to
  the closest segment of the **whole rack network** (spine + water cluster +
  connectors, including the main rack at the PB centre) — not only the PB↔CT spine.

- **[Polygon change] Candidate pruning.** Rack-buffer candidate points that fall
  **outside the polygon** are dropped.

- **[Polygon change] Water-cluster free-end cleanup (§3.6.C-3).** The water spine
  gets the same free-end trimming as the PB/CT spine, but **anchored to the
  water-triangle connection points** (on the RAW/Demi/WWT rack buffers): a trim is
  kept only if the network **still touches every water rack buffer** it touched
  before — otherwise it is reverted. *(Work in progress — still being refined.)*

### §3.7 Perimeter Fire Road — **[Polygon change]**

- The fire road is made by **joining the safety areas of all blocks** into one
  outline, then tracing the outer edge.
- **Before:** the trace was kept inside the **rectangle**.
- **Now:** the trace is kept inside the **polygon**, so the fire road **follows the
  diagonal sides**.
- **The simple version** of the fire road is just the **plot shrunk inward by
  9 m** (this already works on your 5-sided sample and follows the diagonal).

### §3.8 Re-center — **[Polygon change]**

- After everything is placed, the layout is usually not centered.
- The program **moves the plot** (not the buildings) so the plot center lines up
  with the center of all the content.
- **Before:** it slid a rectangle. **Now:** it **moves the whole polygon** (all
  corners) by the same amount.
- The **gate** moves with its side; the gate road's last piece is rebuilt to reach
  the moved gate.

## §4. What Step 1 gives back

The engine returns one data package with everything in it. **[Polygon change]** it
now includes the plot as a **polygon**:

- `blocks`, `ring_road`, `gate_spur`, `ring_spur`, `boom_barrier`
- `rack_segments`, `rack_buffers`, `water_triangle`
- `outer_loop` (the fire road)
- `gate_point`, `gate_death_zone`, `pb_center`
- **`plot_polygon`** — the plot corners (the new shape)
- `plot_bounds` — the box around it (kept so old code still works)

---

# PART III — RULES (scoring)

- Layouts get a **penalty score**: **lower is better, 0 is perfect**.
- Rules check things like: distance to the plot center, setback from the boundary,
  upwind/downwind position, distance between blocks, rack length, road distance.
- **[Polygon change]** Rules that measure **distance to the boundary** now measure
  the distance to the **nearest real side of the polygon** (including diagonals).
- The full rule tables (PB-01, CT-01, etc.) are unchanged — see Part III of
  [`PROJECT.md`](PROJECT.md). Only the boundary distance is measured against the
  polygon.

---

# PART IV — CODE LAYOUT

```
Core/
  Plot.py        [NEW] the plot-shape helper
  CADImport.py  [NEW] reads the CAD file by layer
  Step01.py    the layout engine
  Grid.py        the 2 m grid
  Pathfind.py    road/rack routing (A*)
  Groups.py      block sizes, shapes, colors
Dashboard/
  Road_Test.py   the screen (DXF read from disk + wind setting)
tests/
  test_plot.py   [NEW] automatic checks
Data/
  sample_plot.dxf / .dwg   [NEW] your real drawing
```

## The screen (dashboard)

- **Settings:** **wind direction** only. (A hidden "rectangle fallback" box keeps
  the old sliders for quick rectangle tests.)
- **Plot file:** read **from disk** (browser upload is blocked on your PC). It
  reads `Data/sample_plot.dxf` by default; you can type another path.
- **Preview:** shows the plot outline, the **9 m inset** (fire road preview), the
  center, the gate, the boom, and the buildings (RAW tank is drawn as a circle).

## Where we are

- **Phase 0 is done and checked** against your real drawing.
- The next phases (1–10) connect the polygon into the engine, one at a time. See
  [`PLAN_Polygon_Migration.md`](PLAN_Polygon_Migration.md).

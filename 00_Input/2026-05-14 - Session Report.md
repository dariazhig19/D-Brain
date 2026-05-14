# Session Report — 2026-05-14

## Overview

Two tracks today: (1) research literature scan + deep dive on GlobalMapper,
and (2) replacing the rectangular perimeter road with a grid-based A* router
in `Core/`. The road work runs end-to-end and produces results in the
dashboard; tomorrow continues from there.

---

## Track 1 — Research

### Literature scan
Researched 10 papers across road-to-building layout generation, grid-based
urban planning, parcel filling, generative city blocks, and BIM-integrated
plant layout (2024–2026). Full analysis with algorithms, I/O, metrics, and
PowerPlan AI applicability lives in the conversation history.

**Top 3 to read** (ranked by direct relevance):
1. LLM-Driven A* + NSGA-II for 3D Facility Layout — *ESWA 2026*. Closest
   domain match; co-optimises facilities + channels = your Buildings +
   Pipe Racks problem.
2. GenFusion (Diffusion + GA + XGBoost) — *Information Geography 2025*.
   XGBoost surrogate pattern for replacing the slow scorer inside the GA
   loop.
3. GlobalMapper — *ICCV 2023*. Skeletonization → canonical grid trick
   for arbitrary-shaped blocks.

### GlobalMapper deep dive
- PDF in `02_Library/Generative_Theory/`.
- Reading notes saved to
  `02_Library/Generative_Theory/GlobalMapper_Notes.md` — covers
  architecture, the Canonical Spatial Transform trick, per-node feature
  list, training details, full results table, and PowerPlan AI mapping.
- Key takeaway: their grid is for *training a network on 120k blocks*. With
  0 training data on power-plant layouts, GlobalMapper as-is is not directly
  usable. But the grid representation and CST are reusable patterns for
  later ML adoption.

### Decision on grids for PowerPlan AI
After reviewing the existing engine:
- **Buildings: keep continuous placement.** Real-valued setbacks +
  anisotropic footprints (Cooling Tower 40×183 m) + only 10 entities ⇒
  grid quantisation would degrade scoring fidelity for no real gain.
- **Roads (and later racks): switch to grid-based A*.** Solves the open
  Phase 05 rack-routing item by construction; replaces the brittle
  "deform_around_buildings only handles north edge" code.

---

## Track 2 — Road network rewrite

### Files changed

| File | Status | Purpose |
|---|---|---|
| `Core/Grid.py` | **new** | 2.5 m occupancy grid; world↔cell coords; building/setback marking (vectorised) |
| `Core/Pathfind.py` | **new** | A* with turn-penalty smoothing, width-aware passability, precomputed-passable fast path |
| `Core/Roads.py` | extended | `build_road_network(site_w, site_l, buildings)` — A* perimeter loop. Old `build_perimeter_road` + `deform_around_buildings` kept as fallback. |
| `Core/Main.py` | rewired | Road built per-candidate after buildings (not before); candidate rejected when A* fails |
| `Dashboard/App.py` | render switch | Detects `mode == "astar"`, offsets centerline by ±width/2 to recreate the corridor visual; legacy layouts still render |

### How it works now

For each candidate layout:
1. Place all 10 buildings (continuous, unchanged from before).
2. Build a 2.5 m grid (200×108 for a 500×270 site).
3. Mark every building blocked, inflated by `ROAD_TO_BUILDING = 3 m`.
4. Mark the 5 m setback strip blocked.
5. Erode once to produce a `passable` bool array (corridor of ≥3 cells = 7.5 m wide).
6. Snap 24 waypoints (6 per edge) to the nearest passable cell — this is
   what makes the Gate-House-flush-with-boundary case work.
7. A* between consecutive waypoints, closed loop.
8. On any A* failure → reject candidate.

Result: smooth perimeter road that naturally bulges inward around any
building on any of the 4 edges. No more "north-only" special case.

### Performance fixes applied mid-session

Initial implementation hit ~5 minutes with no results. Three fixes:

- **Vectorised `mark_setback`** in `Grid.py` (numpy bitmask, not Python loop).
- **`build_passable`** added to `Pathfind.py` — precomputes corridor
  passability once per candidate; A* uses O(1) array lookup instead of
  9-cell check per neighbour.
- **`snap_to_passable`** — relocates waypoints that landed inside the
  Gate House's blocked zone. Without this, every candidate with GH on
  north was rejected silently.

After fixes: results return in reasonable time; corridor visible in dashboard.

---

## Tomorrow's open items

### Highest priority — diagnose remaining overlap issues
Daria noted "seems overlap etc problems" before stopping. Likely candidate
rejection is now dominated by something downstream of A*, not A* itself.
First thing to do:
- Add a per-stage rejection counter inside the candidate loop in
  `Core/Main.py` (overlap / road-None / rack-crossing / score-too-low)
  and print after the run. One run tells you the real bottleneck.
- Most likely suspect: building inflation (3 m for road) + rack clearance
  (2.5 m) is over-constrained on tight sites.

### Open work from earlier roadmap (still standing)
1. **Adopt metrics in `!Scoring_Logic.md`:** OPR (overlap %), OBR
   (out-of-block %), L-Sim, GED. Aligns with paper #10 and #6.
2. **XGBoost surrogate for `Rules.py` scoring** — pattern from GenFusion.
   Needs a corpus of (layout → score) pairs first.
3. **Rack routing as grid A*** — apply the same recipe as roads, just at
   width_cells=0 and on the same grid (already returned in the road dict
   for reuse).
4. **Road connectivity scoring** — add a rule that every building is
   reachable by road. Currently the road is geometry, not a constraint.

### Smaller cleanup
- `Core/Exporter.py` likely still reads `outer_polyline`/`inner_polyline`
  and will need similar update when DXF export is re-enabled.
- `_offset_loop` in `Dashboard/App.py` has no miter handling — fine for
  the smooth A* paths but could self-intersect on sharp corners.
- IDE shows "Cannot find module `numpy`" diagnostic in `Grid.py` and
  `Pathfind.py` — false positive from a misconfigured Python interpreter
  in the IDE. numpy 2.4.4 is installed at runtime. Ignore.

---

## Files added/modified summary

```
new:   01_Products/Layout_Gen_Design/Core/Grid.py
new:   01_Products/Layout_Gen_Design/Core/Pathfind.py
mod:   01_Products/Layout_Gen_Design/Core/Roads.py       (+~95 lines, old funcs kept)
mod:   01_Products/Layout_Gen_Design/Core/Main.py        (3 small edits)
mod:   01_Products/Layout_Gen_Design/Dashboard/App.py    (2 edits)

new:   02_Library/Generative_Theory/GlobalMapper_Notes.md
new:   02_Library/Generative_Theory/He_GlobalMapper_..._ICCV_2023_paper.pdf
       (loaded by Daria during session)
```

Nothing committed to git yet — all changes visible via `git diff`.

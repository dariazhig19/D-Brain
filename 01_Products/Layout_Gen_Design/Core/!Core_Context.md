---
type: context
folder: Core
project: PowerPlan AI (Layout_Gen_Design)
---

# Core — Python File Context

This folder contains the engine logic for PowerPlan AI. No UI code lives here.

## Files

### `Main.py`
Entry point and orchestrator. Coordinates calls between Groups and Rules modules to run layout generation iterations and return the best-scored result.
**Phase_03 Implementations:**
- Implemented `generate_layouts()` as a constrained random placement engine.
- Uses diversity filtering to return up to 100 unique candidate layouts.

**Phase_04 Implementations:**
- Placement strategies for all 9 rectangular groups (Power Block, Cooling Tower, Admin Building, Gate House, Cable Tunnel, LPG/Metering, Flare, WT/WWT, Water).
- Each group has a domain-aware placement heuristic (windward, setback, proximity constraints).
- Rack placement: straight lines connecting related groups (Power Block→Cooling Tower, etc.).
- Uses `evaluate_all_v2()` for scoring with 22 rules.

**Phase_05 Implementations:**
- `build_perimeter_road()` (now in `Roads.py`) generates a 7m wide perimeter fire road (5m setback from boundary).
- Hierarchical placement order: GH(fixed user-chosen edge) → GIS(fixed user-chosen corner) → PB(center) → Admin → CT → WT/WWT → Water → Flare → LPG → Warehouse.
- Gate House and GIS are pinned (not randomized). Power Block has ±5% jitter.
- All buildings respect road corridor clearance (15m from boundary = 5m setback + 7m road + 3m gap).
- `_place_warehouse()` uses collision-aware placement against all already-placed buildings.
- Cable Tunnel rack: GIS ↔ Power Block.
- Layout output includes `"road"` key with perimeter road geometry.
- **Building rotation (random 0°/90°):** placement tuples now `(x, y, rotated)`. Non-square, non-fixed buildings randomly rotate. Fixed/pinned buildings (GH, GIS) and square footprints (PB, Water, Flare) never rotate. Helpers: `_dims(name, rotated)`, `_maybe_rotate(name)`.
- **Fixed-anchor inputs:** `generate_layouts(..., gate_house_side="N", gis_corner="NE")`. GH accepts `N/S/E/W`; GIS accepts `NE/NW/SE/SW`. Defaults preserve prior behavior.
- **Road deformation (step 2 minimal):** after `build_perimeter_road`, `Main.py` calls `deform_around_buildings(road, [Gate House], …)` from `Roads.py`. The resulting road dict carries `outer_polyline`/`inner_polyline`. Only Gate House drives deformation for now; other boundary-hugging buildings come later.

### `Geometry.py`
Handles all spatial/geometric operations: drawing site boundaries, placing building rectangles, computing distances between objects, and checking boundary containment. Uses Matplotlib patches as the rendering primitive. **Status: stub — not yet implemented.**

### `Roads.py` *(New, Phase_05 step 2)*
Owns road infrastructure: dimensional constants and geometry generation.
- **Constants** (migrated out of `Rules.py`): `ROAD_WIDTH=7`, `ROAD_SETBACK=5`, `ROAD_TO_BUILDING=3`, `ROAD_TO_RACK=2`, `RACK_TO_BLOCK=2.5`, `ROAD_INNER_EDGE=12`, `MIN_BUILDING_FROM_BOUNDARY=15`.
- `build_perimeter_road(site_w, site_l)` — migrated from `Main.py`. Returns dict with `outer`/`inner` rectangle corners.
- `deform_around_buildings(road, buildings, site_w, site_l)` — bends the perimeter road inward around buildings that intrude into the corridor. Currently handles the **north (top) edge only** (Phase_05 step 2 minimal). Adds `outer_polyline` and `inner_polyline` closed-loop point lists to the road dict; corridor width preserved at `ROAD_WIDTH`.
- Other 3 edges (S/E/W) remain rectangular — to be expanded in future steps.

### `Rules.py`
Translates engineering constraints into Python validation functions.
**Phase_03 Implementations:**
- 6 hand-coded rule functions (PB-01 through AD-02) — kept for backward compatibility.
- Each rule returns a standardized dictionary (`measured`, `threshold`, `calc`) for UI transparency.
- Orchestrator function `evaluate_all()` aggregates scores and maps violations per building.

**Phase_04 Implementations:**
- Added `RULES` data list — mirrors `!Scoring_Logic.md` table. Each dict maps 1:1 to a row.
- 6 generic evaluator functions dispatched by **Rule Type**:
  - `_eval_center_proximity()` — building center vs plot center
  - `_eval_boundary_setback()` — min edge distance to site boundary
  - `_eval_windward_edge()` — building on windward side check
  - `_eval_min_distance()` — center-to-center distance ≥ threshold
  - `_eval_max_distance()` — center-to-center distance ≤ threshold
  - `_eval_pipe_rack_proximity()` — building to rack line distance
- `evaluate_all_v2()` loops `RULES`, dispatches to matching generic function.
- 22 total rules (6 Phase 03 + 16 Phase 04).

**Phase_05 Implementations:**
- Road infrastructure constants moved to `Roads.py`. `Rules.py` now imports `ROAD_INNER_EDGE` from `Roads.py` for `_eval_road_proximity`.
- 2 new evaluator functions:
  - `_eval_road_proximity()` — building edge to perimeter road inner edge distance
  - `_eval_boundary_overflow()` — logarithmic penalty for boundary overflow
- 8 new rules: GIS-01, WH-01, RD-01/02/03, CT-03 (Cable Tunnel GIS↔PB).
- Total: 30 rules (22 Phase 04 + 8 Phase 05).
- `_EVALUATORS` dispatch table expanded with `road_proximity` and `boundary_overflow`.

### `Exporter.py`
**Phase_03 Implementations:**
- Converts layout geometry to a 7-layer DXF CAD file at 1:1 scale using `ezdxf`.
- Zero Streamlit imports, completely independent CAD writing logic.

**Phase_04 Implementations:**
- Added DXF layers for all 9 new groups + 3 rack types.
- Polyline rack export as DXF lines.
- Dynamic rule count in score annotation.

### `Groups.py`
Defines building groups as data structures with dimensions, color codes, and positions.
**Phase_02 Implementations (The Three Giants):**
- `get_groups()` accepts absolute `x` and `y` coordinates.
- `draw_group(ax, group)` uses `ax.plot` and `ax.fill` for DXF-ready coordinate export.

**Phase_04 Implementations:**
- Added `FOOTPRINTS` catalog: 9 rectangular groups with estimated dimensions.
- Added `RACK_WIDTHS` / `RACK_COLORS` for 3 polyline racks.
- `get_all_groups(site_w, site_l, positions=None)` — returns all 9 rectangle groups.
- `get_all_racks(groups, rack_endpoints=None)` — returns 3 polyline racks as straight lines.
- `draw_rack(ax, rack)` — renders racks as dashed thick lines with labels.
- `get_groups()` kept for Phase 03 backward compatibility.

**Phase_05 Implementations:**
- Updated `FOOTPRINTS` with client-confirmed dimensions (PB 150×150, CT 40×183, etc.).
- Added 2 new groups: **GIS** (110×51) and **Warehouse** (59×40).
- Total: 11 rectangular groups.
- Updated `GROUP_COLORS` for GIS and Warehouse.
- Updated default positions in `get_all_groups()` for 500×270 site.
- `get_all_groups()` accepts 3-tuple `(x, y, rotated)` positions; when `rotated=True`, swaps `(width, height)` for 90° rotation. Group dicts now include `rotated` key.

### `RuleNetwork.py` *(New in Phase_04)*
Standalone script for rule network visualization.
- Reads `RULES` list from `Rules.py`.
- Builds `networkx.Graph`: nodes = groups/racks, edges = rules.
- Exports interactive Pyvis HTML to `Notes/Rule_Network.html`.
- Dark theme, color-coded edges by Rule Type, floating legend.
- Run: `python Core/RuleNetwork.py`

## Key Design Principles
- Core has zero Streamlit imports — it must be callable independently of the dashboard.
- Scoring is additive: each rule contributes a penalty, lower total = better layout.
- Phase_05 milestone: Infrastructure-first placement with perimeter road, hierarchical building order, Cable Tunnel connection.

## Daily Changes

| Date                      | File                                 | Change                                                     |
| ------------------------- | ------------------------------------ | ---------------------------------------------------------- |
| [[Daily_Report_20260428]] | `Main.py`, `Geometry.py`, `Rules.py` | Initialized as empty stubs. Project structure established. |
| [[Daily_Report_20260429]] | `!Core_Context.md` | Renamed from !Context.md; updated to match new naming convention. |
| [[Daily_Report_20260430]] | `Groups.py` | Implemented Phase 2 logic. Refactored from offsets (dx) to bounded absolute coordinates (x). |
| [[Daily_Report_20260506]] | `Rules.py`, `Main.py`, `Exporter.py` | Implemented Phase 03: generative engine, rule logic orchestrator, and DXF exporter module. |
| [[Daily_Report_20260507]] | `Rules.py`, `Groups.py`, `Main.py`, `Exporter.py`, `RuleNetwork.py` | Implemented generic rule dispatch engine and 22-rule constraint list. Expanded catalog to 12 total groups (9 rects, 3 racks). Updated layout generation orchestrator for 12 groups. Added new DXF layer definitions and polyline export logic. Created Pyvis network generation script. |
| 2026-05-13 | `Groups.py`, `Rules.py`, `Main.py` | **Phase 05:** Updated all building dimensions to client-confirmed values. Added GIS (110×51) and Warehouse (59×40). Added road infrastructure (7m road, 5m setback). Hierarchical placement: GH fixed N-center, GIS fixed NE, PB center. 8 new rules (30 total). Cable Tunnel connects GIS↔PB. |
| 2026-05-13 | `Main.py`, `Groups.py` | **Phase 05.1:** Added random 0°/90° rotation for non-square, non-fixed buildings. Placement tuples now `(x, y, rotated)`. `get_all_groups()` swaps W/H when rotated. |
| 2026-05-13 | `Main.py`, `App.py` | **Phase 05.2:** Added `gate_house_side` (N/S/E/W) and `gis_corner` (NE/NW/SE/SW) inputs to `generate_layouts`; wired to new sidebar "Fixed Anchors" section. |
| 2026-05-13 | `Roads.py`, `Rules.py`, `Main.py`, `App.py` | **Phase 05 step 2:** New `Core/Roads.py` module owns road constants + geometry. Migrated `build_perimeter_road` out of `Main.py` and constants out of `Rules.py`. Added `deform_around_buildings()` — bends top edge inward around Gate House (other edges TBD). Road dict now carries `outer_polyline`/`inner_polyline`. App.py road drawing rewritten to read polylines from layout dict. |

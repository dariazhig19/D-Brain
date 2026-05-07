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

### `Geometry.py`
Handles all spatial/geometric operations: drawing site boundaries, placing building rectangles, computing distances between objects, and checking boundary containment. Uses Matplotlib patches as the rendering primitive. **Status: stub — not yet implemented.**

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
- Phase_04 milestone: Generic rule engine with `RULES` data list mirroring `!Scoring_Logic.md`.

## Daily Changes

| Date                      | File                                 | Change                                                     |
| ------------------------- | ------------------------------------ | ---------------------------------------------------------- |
| [[Daily_Report_20260428]] | `Main.py`, `Geometry.py`, `Rules.py` | Initialized as empty stubs. Project structure established. |
| [[Daily_Report_20260429]] | `!Core_Context.md` | Renamed from !Context.md; updated to match new naming convention. |
| [[Daily_Report_20260430]] | `Groups.py` | Implemented Phase 2 logic. Refactored from offsets (dx) to bounded absolute coordinates (x). |
| [[Daily_Report_20260506]] | `Rules.py`, `Main.py`, `Exporter.py` | Implemented Phase 03: generative engine, rule logic orchestrator, and DXF exporter module. |
| [[Daily_Report_20260507]] | `Rules.py`, `Groups.py`, `Main.py`, `Exporter.py`, `RuleNetwork.py` | Implemented generic rule dispatch engine and 22-rule constraint list. Expanded catalog to 12 total groups (9 rects, 3 racks). Updated layout generation orchestrator for 12 groups. Added new DXF layer definitions and polyline export logic. Created Pyvis network generation script. |

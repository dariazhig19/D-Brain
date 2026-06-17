---
type: context
folder: Dashboard
project: PowerPlan AI (Layout_Gen_Design)
---

# Dashboard — Python File Context

This folder contains the Streamlit web UI. All user-facing interaction lives here.

## Files

### `App.py`
Main Streamlit application. Currently implements **Phase_04**:
- Sidebar sliders: `Plot Width (A)` and `Plot Length (B)` — range 100–1000m, step 10m.
- Renders site boundary as X,Y coordinate lines via `ax.plot()` — future-ready for line export.
- Renders primary road setback as X,Y coordinate lines (dashed red, 5m inset).
- Font: `Malgun Gothic` (Windows pre-installed) + `axes.unicode_minus = False` for correct minus rendering.
- Figures rendered as base64 HTML `<img>` via `_fig_to_b64()` helper for precise centering.
- Multi-column grid layout: `NUM_COLS = 4` — ready for multi-phase plot display.
- Hidden axes ticks and spine frame.
- Page title: "PowerPlan AI: Layout Generator", layout: wide.

**Phase_02 Implementations (The Three Giants):**
- Imports the 3 building groups from `Core.Groups`.
- Bounded sliders guarantee buildings cannot be dragged outside the plot.
- Added "Wind Direction" selectbox to "Site Information".
- Updated rendering engine for responsiveness (`width: 100%`) and higher resolution.

**Phase_03 Implementations (Generative Engine & Visualization):**
- Replaced manual coordinate sliders with automated `generate_layouts()` flow.
- Added thumbnail grid to display up to 100 candidate layouts visually.
- Added Detailed Rule Inspector (`st.expander`) displaying `measured`, `threshold`, and `calc` logic.
- Integrated `Core.Exporter` for DXF file download directly from the UI.
- On-plot visual annotations: crimson dashed borders for rule violations.

**Phase_04 Implementations (New Groups & Generic Rules):**
- Renders all 12 groups: 9 colored rectangles + 3 dashed polyline racks.
- Uses `evaluate_all_v2()` with dynamic `RULES` list (22 rules).
- Rack violation overlays (crimson solid lines for failing racks).
- Min rules passing slider range dynamically bound to `len(RULES)`.
- Header updated to "Phase_04: New Groups & Generic Rules".

**Phase_05 Implementations (Infrastructure-First):**
- Default site dimensions updated: Width=500, Length=270.
- Phase header updated to "Phase_05: Infrastructure-First Layout Engine".
- Perimeter road rendered as filled gray corridor (7m wide, 5m setback from boundary).
- Replaced red dashed road setback with dual-edge road corridor visualization.
- Renders all 11 groups including new GIS and Warehouse blocks.

**Phase_05 step 2 Implementations:**
- New sidebar section **Fixed Anchors**: `Gate House edge` selectbox (`N/S/E/W`) and `GIS corner` selectbox (`NE/NW/SE/SW`). Passed to `generate_layouts(..., gate_house_side, gis_corner)`.
- Road rendering rewritten to read `outer_polyline` and `inner_polyline` from `layout["road"]` (drawn by `Core.Roads.deform_around_buildings`). Allows non-rectangular roads (e.g., deformed around Gate House).
- Imports simplified — road constants no longer needed in App.py; `build_perimeter_road` import dropped.

## Key Design Principles
- Dashboard calls Core functions only — no geometry/rules logic lives in App.py.
- Each sidebar control section is clearly commented.
- `st.set_page_config` must be the first Streamlit call in the file.

## Daily Changes

| Date                      | File     | Change                                                                                                                      |
| ------------------------- | -------- | --------------------------------------------------------------------------------------------------------------------------- |
| [[Daily_Report_20260428]] | `App.py` | Created Phase_01 Streamlit app — site boundary rectangle + 5m road setback dashed overlay, sidebar sliders for width/length. |
| [[Daily_Report_20260429]] | `!Dashboard_Context.md` | Renamed from !Context.md; updated to match new naming convention. |
| [[Daily_Report_20260430]] | `App.py` | X,Y lines update. Added absolute bounded sliders, Wind input, high-res rendering and fixed legend clipping. |
| [[Daily_Report_20260506]] | `App.py` | Rewrote for Phase 03 generative layout, grid display, rule inspector, and DXF export. |
| [[Daily_Report_20260507]] | `App.py` | Added rack visualization and dynamic rule inspector. |
| [[Daily_Report_20260513]] | `App.py` | Phase 05 UI: Added Fixed Anchor sidebar section and polyline road rendering logic. |
| [[Daily_Report_20260518]] | `App.py`, `Roads_Test.py` | Implemented circular rendering for RAW Water Tank and Flare using ax.add_patch(plt.Circle). Updated test dashboard to visually reflect true road widths and draw explicit A* cell footprints. |

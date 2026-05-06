---
type: context
folder: Dashboard
project: PowerPlan AI (Layout_Gen_Design)
---

# Dashboard — Python File Context

This folder contains the Streamlit web UI. All user-facing interaction lives here.

## Files

### `App.py`
Main Streamlit application. Currently implements **Phase_01**:
- Sidebar sliders: `Plot Width (A)` and `Plot Length (B)` — range 100–1000m, step 10m.
- Renders site boundary as X,Y coordinate lines via `ax.plot()` — future-ready for line export.
- Renders primary road setback as X,Y coordinate lines (dashed red, 5m inset).
- Font: `Malgun Gothic` (Windows pre-installed) + `axes.unicode_minus = False` for correct minus rendering.
- Fixed pixel-size figures: `500×300 px` at 100 dpi — no browser-scale distortion.
- Figures rendered as base64 HTML `<img>` via `render_centered()` helper for precise centering.
- Multi-column grid layout: `NUM_COLS = 4` — ready for multi-phase plot display.
- Hidden axes ticks and spine frame; legend placed below plot.
- Page title: "PowerPlan AI: Layout Generator", layout: wide.

**Phase_02 Implementations (The Three Giants):**
- Imports the 3 building groups from `Core.Groups`.
- Replaced offset sliders with absolute bounded X/Y coordinate sliders for each group.
- Bounded sliders guarantee buildings cannot be dragged outside the plot (`min_value=0`, `max_value=site_width - building_width`).
- Added "Wind Direction" selectbox to "Site Information" and rendered a visual text indicator on the Matplotlib plot.
- Updated rendering engine for responsiveness (`width: 100%`) and higher resolution (`800x600`).
- Moved Matplotlib Legend completely inside the axes bounds (`loc='lower center'`) with expanded `ylim` padding (`-40`) to fix clipping issues with `tight_layout()`.
- Added `importlib.reload(Core.Groups)` to ensure hot-reloading works properly without Streamlit cache `TypeError`s.

**Phase_03 Implementations (Generative Engine & Visualization):**
- Replaced manual coordinate sliders with automated `generate_layouts()` flow.
- Added 5-column thumbnail grid to display up to 100 candidate layouts visually.
- Added Detailed Rule Inspector (`st.expander`) displaying `measured`, `threshold`, and `calc` logic for transparent penalty breakdowns.
- Integrated `Core.Exporter` for DXF file download directly from the UI.
- On-plot visual annotations: crimson dashed borders for rule violations, dashed inter-building distance lines, double-headed setback brackets, and fixed Gate House drawing.

## Key Design Principles
- Dashboard calls Core functions only — no geometry/rules logic lives in App.py.
- Each sidebar control section is clearly commented (`# --- UI CONTROLS ---`, `# --- CORE ENGINE ---`, `# --- DISPLAY ---`).
- `st.set_page_config` must be the first Streamlit call in the file.

## 📅 Daily Changes

| Date                      | File     | Change                                                                                                                      |
| ------------------------- | -------- | --------------------------------------------------------------------------------------------------------------------------- |
| [[Daily_Report_20260428]] | `App.py` | Created Phase_01 Streamlit app — site boundary rectangle + 5m road setback dashed overlay, sidebar sliders for width/length. |
| [[Daily_Report_20260429]] | `!Dashboard_Context.md` | Renamed from !Context.md; updated to match new naming convention. |
| [[Daily_Report_20260430]] | `App.py` | X,Y lines update. Added absolute bounded sliders, Wind input, high-res rendering and fixed legend clipping. |
| [[Daily_Report_20260506]] | `app.py` | Rewrote for Phase 03 generative layout, grid display, rule inspector, and DXF export. |

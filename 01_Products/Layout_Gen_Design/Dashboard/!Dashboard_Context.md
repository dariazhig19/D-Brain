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

**Next Phase_02 additions here:** render Power Block, Cooling Tower, Admin Building as colored blocks with X/Y sliders.

## Key Design Principles
- Dashboard calls Core functions only — no geometry/rules logic lives in App.py.
- Each sidebar control section is clearly commented (`# --- UI CONTROLS ---`, `# --- CORE ENGINE ---`, `# --- DISPLAY ---`).
- `st.set_page_config` must be the first Streamlit call in the file.

## 📅 Daily Changes

| Date                      | File     | Change                                                                                                                      |
| ------------------------- | -------- | --------------------------------------------------------------------------------------------------------------------------- |
| [[Daily_Report_20260428]] | `App.py` | Created Phase_01 Streamlit app — site boundary rectangle + 5m road setback dashed overlay, sidebar sliders for width/length. |
| [[Daily_Report_20260429]] | `!Dashboard_Context.md` | Renamed from !Context.md; updated to match new naming convention. |
| [[Daily_Report_20260430]] | `App.py` | Switched geometry from patches to X,Y coordinate lines (`ax.plot`); all comments English-only. |

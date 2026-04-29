---
type: context
folder: Dashboard
project: PowerPlan AI (Layout_Gen_Design)
---

# Dashboard — Python File Context

This folder contains the Streamlit web UI. All user-facing interaction lives here.

## Files

### `App.py`
Main Streamlit application. Currently implements **Phase 1**:
- Sidebar sliders: `Plot Width (A)` and `Plot Length (B)` — range 100–1000m, step 10m.
- Renders site boundary as a filled light-blue rectangle using `matplotlib.patches.Rectangle`.
- Renders primary road setback as a dashed red rectangle inset 5m from the boundary.
- Uses `ax.set_aspect('equal')` to prevent distortion at any slider value.
- Page title: "PowerPlan AI: Layout Generator", layout: wide.

**Next Phase 2 additions here:** render Power Block, Cooling Tower, Admin Building as colored blocks with X/Y sliders.

## Key Design Principles
- Dashboard calls Core functions only — no geometry/rules logic lives in App.py.
- Each sidebar control section is clearly commented (`# --- UI CONTROLS ---`, `# --- CORE ENGINE ---`, `# --- DISPLAY ---`).
- `st.set_page_config` must be the first Streamlit call in the file.

## 📅 Daily Changes

| Date | File | Change |
|------|------|--------|
| [[Daily_Report_20260428]] | `App.py` | Created Phase 1 Streamlit app — site boundary rectangle + 5m road setback dashed overlay, sidebar sliders for width/length. |

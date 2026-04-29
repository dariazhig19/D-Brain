---
type: context
folder: Core
project: PowerPlan AI (Layout_Gen_Design)
---

# Core — Python File Context

This folder contains the engine logic for PowerPlan AI. No UI code lives here.

## Files

### `Main.py`
Entry point and orchestrator. Will coordinate calls between Geometry and Rules modules to run layout generation iterations and return the best-scored result. **Status: stub — not yet implemented.**

### `Geometry.py`
Handles all spatial/geometric operations: drawing site boundaries, placing building rectangles, computing distances between objects, and checking boundary containment. Uses Matplotlib patches as the rendering primitive. **Status: stub — not yet implemented.**

### `Rules.py`
Translates engineering constraints from `Plot plan requirement.xlsx` into Python validation functions. Each rule returns a pass/fail + penalty score. Examples: minimum setback from site boundary (5m primary road), minimum distance between Power Block and Admin Building (50m). **Status: stub — not yet implemented.**

## Key Design Principles
- Core has zero Streamlit imports — it must be callable independently of the dashboard.
- Scoring is additive: each rule contributes a penalty, lower total = better layout.
- Phase_03 milestone: Rules.py functional with distance checks and visual RED alerts in dashboard.

## 📅 Daily Changes

| Date                      | File                                 | Change                                                     |
| ------------------------- | ------------------------------------ | ---------------------------------------------------------- |
| [[Daily_Report_20260428]] | `Main.py`, `Geometry.py`, `Rules.py` | Initialized as empty stubs. Project structure established. |

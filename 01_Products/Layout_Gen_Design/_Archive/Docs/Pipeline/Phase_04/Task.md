# Phase 04 — Execution Checklist

- [x] **Step 1:** `!Scoring_Logic.md` — added Rule Type column + Phase 04 rules (22 total)
- [x] **Step 2:** `Core/Groups.py` — added 6 new rectangle groups + 3 polyline racks (12 total)
- [x] **Step 3:** `Core/Rules.py` — added `RULES` data list (22 rules) + 6 generic evaluators + `evaluate_all_v2()`
- [x] **Step 4:** `Core/Main.py` — rebuilt placement engine for all 12 groups
- [x] **Step 5:** `Core/RuleNetwork.py` + `pip install pyvis networkx` — generates `Notes/Rule_Network.html` (15 nodes, 20 edges)
- [x] **Step 6:** `Dashboard/App.py` — renders all 12 groups + polyline racks
- [x] **Step 7:** `Core/Exporter.py` — added new DXF layers + rack polylines
- [x] **Step 8:** Updated context docs (`!Dashboard_Context.md`, `!Core_Context.md`)

## Verification Results
- `Groups.py`: 9 groups + 3 racks load correctly
- `Rules.py`: 22 rules evaluate correctly (all dispatched by Rule Type)
- `Main.py`: generates 3+ layouts in <2 seconds
- `RuleNetwork.py`: generates HTML with 15 nodes, 20 edges
- `App.py`: Streamlit dashboard starts on port 8503, renders all groups

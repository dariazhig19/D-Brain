# Phase 3: Rules Engine & Visual RED Alerts

## Goal
Make `Rules.py` fully functional: evaluate the 6 constraints from `!Scoring_Logic.md`,
compute a total penalty score, and visually flag violations with **RED overlays and warnings**
directly on the Matplotlib plot in the Dashboard.

---

## Background

Phase 2 delivered interactive building placement (The Three Giants).  
Phase 3 activates the rule engine that **scores** those placements in real time.

Rules defined in `!Scoring_Logic.md` (Phase 2 table):

| ID | Group | Constraint | Penalty |
|---|---|---|---|
| PB-01 | Power Block | Distance from plot center | 100 pts/m |
| PB-02 | Power Block | Setback ≥ 5m from road | 5000 pts (flat) |
| CT-01 | Cooling Tower | Must be on windward edge | 1000 pts (flat) |
| CT-02 | Cooling Tower | Distance to Admin ≥ 50m | 500 pts/m under |
| AD-01 | Admin Building | Distance to primary road ≥ 20m | 1000 pts (flat) |
| AD-02 | Admin Building | Distance to Gate (site edge) ≤ 50m | 100 pts/m over |

---

## Proposed Changes

### Core Layer

#### [MODIFY] [Rules.py](file:///x:/CST본부%20(구%20기술지원부%20폴더)/15.%20다리아/D-Brain/01_Products/Layout_Gen_Design/Core/Rules.py)

Implement all 6 rules as individual functions. Each returns a dict:
```python
{"id": "PB-01", "passed": bool, "penalty": float, "message": str}
```

Top-level `evaluate_all(groups, site_width, site_length, wind_dir)` returns:
```python
{"results": [...], "total_penalty": float}
```

---

### Dashboard Layer

#### [MODIFY] [app.py](file:///x:/CST본부%20(구%20기술지원부%20폴더)/15.%20다리아/D-Brain/01_Products/Layout_Gen_Design/Dashboard/app.py)

1. **Import & call** `evaluate_all(groups, ...)` after groups are built.
2. **RED Violation Overlay**: If a group has a failing rule, re-draw its border in `red` with increased `linewidth` and dashed style — without modifying `draw_group()` in Core.
3. **Score Panel** below the plot: Show a styled `st.metric` for **Total Penalty Score** + a compact rule-result table (✅ PASS / ❌ FAIL + penalty).

---

### Pipeline

#### [MODIFY] [Phase 03 Notes.md](file:///x:/CST본부%20(구%20기술지원부%20폴더)/15.%20다리아/D-Brain/01_Products/Layout_Gen_Design/Pipeline/Phase_03/Phase%2003%20Notes.md) [NEW FILE]

Document phase goals, decisions, and constraints implemented.

---

## Visual Design (Score Panel)

```
┌─────────────────────────────────────────────┐
│  🏆 Total Penalty Score:   3,200 pts        │
├──────┬─────────────┬──────────┬─────────────┤
│  ID  │ Rule        │ Status   │ Penalty     │
├──────┼─────────────┼──────────┼─────────────┤
│ PB-01│ Center dist │ ✅ PASS  │ 0           │
│ PB-02│ Road setback│ ❌ FAIL  │ 5,000       │
│ CT-01│ Windward    │ ✅ PASS  │ 0           │
│ CT-02│ CT↔Admin   │ ❌ FAIL  │ 2,500       │
│ AD-01│ Admin road  │ ✅ PASS  │ 0           │
│ AD-02│ Admin gate  │ ✅ PASS  │ 0           │
└──────┴─────────────┴──────────┴─────────────┘
```

---

## Verification Plan

### Automated
- Run `streamlit run app.py` and manually drag groups to trigger each violation.
- Verify RED border appears on the violating building.
- Verify score panel updates in real time.

### Per Rule
| Rule | How to trigger |
|---|---|
| PB-01 | Drag Power Block away from center |
| PB-02 | Drag Power Block to x=0 (touching boundary) |
| CT-01 | Drag Cooling Tower to opposite side of wind |
| CT-02 | Drag Admin and CT close together |
| AD-01 | Drag Admin Building to y=0 |
| AD-02 | Drag Admin far from site bottom-center |

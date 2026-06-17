# Phase 03 Notes — Rules Engine & Generative Layout

## Goal
Activate the penalty-scoring rule engine, visually display violations, and implement an automated generative layout engine with CAD export capabilities.

## Rules Implemented

| ID | Group | Constraint | Penalty Type | Logic |
|---|---|---|---|---|
| PB-01 | Power Block | Center proximity | 100 pts/m from plot center | Euclidean distance, center-to-center **(±20m tolerance zone)** |
| PB-02 | Power Block | 5m road setback | 5,000 pts flat | Any edge closer than 5m to site boundary |
| CT-01 | Cooling Tower | Windward edge placement | 1,000 pts flat | Must be within 30m of the windward side |
| CT-02 | Cooling Tower | ≥50m from Admin | 500 pts/m shortfall | Center-to-center distance |
| AD-01 | Admin Building | ≥20m from road | 1,000 pts flat | Min distance of any edge to site boundary |
| AD-02 | Admin Building | ≤50m from Gate House | 100 pts/m excess | Gate House assumed at (site_width/2, 0) |

## Architecture Decisions

- **`Rules.py` is stateless** — no Streamlit imports, callable independently.
- Each rule returns a standardized dict: `{id, name, group, passed, penalty, message, measured, threshold, calc}` for full transparency.
- `evaluate_all()` returns `violations_by_group` dict for direct use by the dashboard overlay.
- **Generative Engine (`Core/Main.py`)**: Uses constrained random placement (e.g., CT forced to windward zone, Admin forced near gate) + a diversity filter to generate up to 100 unique candidate layouts.
- **CAD Export (`Core/Exporter.py`)**: Uses `ezdxf` to generate true 1:1 scale DXF files. Zero Streamlit UI dependencies in the core exporter logic.

## Visual Outputs
- **Main Dashboard Grid**: Shows up to 100 generated layout thumbnails ranked by penalty score.
- **Rule Inspector**: Dropdown to select a layout and view an expandable breakdown of all 6 rules (showing measured values vs thresholds).
- **On-Plot Annotations**:
  - Violating buildings: **crimson dashed border** + `⚠ rule-id` badge.
  - Dashed inter-building distance lines (Red if rule violated, Gray if neutral).
  - Double-headed setback brackets (Green if passing, Red if violating).
- **DXF Output**: Downloadable CAD file with 7 distinct named layers (Boundary, Setbacks, Gate House, Buildings, Dimensions, Labels).

## Open Items for Phase 04
- [ ] Implement `Rules.py` auto-parsing from `!Scoring_Logic.md` (Phase 4 note in the file).
- [ ] Excel Integration: Parse all 60+ items from `Plot plan requirement.xlsx`.
- [ ] Add Gate House as an actual placed building with its own constraint rules.

---

# Implementation Plan Archive

*The following is the original technical implementation plan drawn up at the beginning of Phase 3, retained here for historical tracking.*

## Goal
Make `Rules.py` fully functional: evaluate the 6 constraints from `!Scoring_Logic.md`,
compute a total penalty score, and visually flag violations with **RED overlays and warnings**
directly on the Matplotlib plot in the Dashboard.

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

## Proposed Changes

### Core Layer

#### `Rules.py`
Implement all 6 rules as individual functions. Each returns a dict:
```python
{"id": "PB-01", "passed": bool, "penalty": float, "message": str}
```

Top-level `evaluate_all(groups, site_width, site_length, wind_dir)` returns:
```python
{"results": [...], "total_penalty": float}
```

### Dashboard Layer

#### `app.py`
1. **Import & call** `evaluate_all(groups, ...)` after groups are built.
2. **RED Violation Overlay**: If a group has a failing rule, re-draw its border in `red` with increased `linewidth` and dashed style — without modifying `draw_group()` in Core.
3. **Score Panel** below the plot: Show a styled `st.metric` for **Total Penalty Score** + a compact rule-result table (✅ PASS / ❌ FAIL + penalty).

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

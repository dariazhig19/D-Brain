# Phase 03 Notes — Rules Engine & Visual Alerts

## Goal
Activate the penalty-scoring rule engine and make violations **visually evident** on the plot and in a live score panel below.

## Rules Implemented

| ID | Group | Constraint | Penalty Type | Logic |
|---|---|---|---|---|
| PB-01 | Power Block | Center proximity | 100 pts/m from plot center | Euclidean distance, center-to-center |
| PB-02 | Power Block | 5m road setback | 5,000 pts flat | Any edge closer than 5m to site boundary |
| CT-01 | Cooling Tower | Windward edge placement | 1,000 pts flat | Must be within 30m of the windward side |
| CT-02 | Cooling Tower | ≥50m from Admin | 500 pts/m shortfall | Center-to-center distance |
| AD-01 | Admin Building | ≥20m from road | 1,000 pts flat | Min distance of any edge to site boundary |
| AD-02 | Admin Building | ≤50m from Gate House | 100 pts/m excess | Gate House assumed at (site_width/2, 0) |

## Architecture Decisions

- **`Rules.py` is stateless** — no Streamlit imports, callable independently.
- Each rule returns a standardized dict: `{id, name, group, passed, penalty, message}`.
- `evaluate_all()` returns `violations_by_group` dict for direct use by the dashboard overlay.
- **RED overlay is drawn in `app.py`**, not in `draw_group()` — keeps Core free of UI-state logic.
- Gate House position is a Phase 03 assumption; will be replaced by an actual building in a future phase.

## Visual Outputs
- Violating buildings: **crimson dashed border** + `⚠ rule-id` badge above the building.
- Below the plot: 3 top-level metrics (total penalty, rules passing, rules failing).
- Detailed rule results table with status icon, penalty amount, and detail message.

## Open Items for Phase 04
- [ ] Implement `Rules.py` auto-parsing from `!Scoring_Logic.md` (Phase 4 note in the file).
- [ ] Add Gate House as an actual placed building with its own slider.
- [ ] `Main.py` orchestrator: iterate N random layouts and return the best-scoring one.

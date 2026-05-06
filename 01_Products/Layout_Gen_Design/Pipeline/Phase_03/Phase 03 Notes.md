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

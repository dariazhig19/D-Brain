# Phase 05: Industrial Infrastructure Integration

## Goals & Objectives
- Transition to an infrastructure-first design philosophy.
- Implement a 7m wide perimeter fire road with a 5m setback from the site boundary.
- Establish a hierarchical placement sequence using "Fixed Anchors" (Gate House and GIS).
- Update all building dimensions to client-confirmed values.
- Expand the rule engine to handle infrastructure proximity and boundary overflow.

## Key Decisions & Architecture
- **Road Deformation**: The perimeter road is no longer a simple rectangle. It dynamically "bends" inward to accommodate the Gate House on the North edge. This is handled by `Core/Roads.py`.
- **Fixed Anchors**: Gate House (Side) and GIS (Corner) are now user-selectable inputs that anchor the generative engine's starting state.
- **Hierarchical Sequence**: 
    1. Gate House (Pinned)
    2. GIS (Pinned)
    3. Power Block (Center Jitter)
    4. Admin, Cooling Tower, etc. (Heuristic-based)
- **Rotation**: Non-square buildings (Admin, Cooling Tower, LPG, etc.) now have random 0°/90° rotation to maximize site efficiency.

## Rule Engine Expansion
- Added `road_proximity` rule to ensure buildings maintain a 3m gap from the fire road.
- Added `boundary_overflow` rule with a logarithmic penalty to discourage but allow tight boundary fits.
- Total rules increased from 22 to 30.

## Output Verification
- Confirmed that the Gate House stays on the selected site edge and is correctly surrounded by the deformed road corridor.
- Verified that the GIS block anchors the NE/NW/SE/SW corner as requested.
- Candidate layouts now show a high diversity of building orientations.

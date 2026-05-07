# ⚖️ Rule Engine: Penalty Scoring Logic

This document is the **Single Source of Truth** for all layout rules.
The generative design system evaluates layouts by calculating a **Total Penalty Score**. 
*Lower score = Better layout.* 
A score of `0` means a perfect layout with no rule violations.

## 📖 Available Rule Types

Each rule has a **Rule Type** that maps to a generic evaluator function in `Rules.py`.

| Rule Type             | Function in Rules.py        | What it checks                                    | Penalty Mode |
| :-------------------- | :-------------------------- | :------------------------------------------------ | :----------- |
| `center_proximity`    | `_eval_center_proximity()`  | Distance from building center to plot center       | Linear       |
| `boundary_setback`    | `_eval_boundary_setback()`  | Min distance from any edge to site boundary        | Flat         |
| `windward_edge`       | `_eval_windward_edge()`     | Is building on the windward side of the plot?      | Flat         |
| `min_distance`        | `_eval_min_distance()`      | Center-to-center distance must be ≥ threshold      | Linear       |
| `max_distance`        | `_eval_max_distance()`      | Center-to-center distance must be ≤ threshold      | Linear       |
| `leeward_edge`        | `_eval_leeward_edge()`      | Is building on the downwind (leeward) side?        | Flat         |
| `pipe_rack_proximity` | `_eval_pipe_rack_proximity()` | Distance from building edge to nearest rack line | Linear       |

**Penalty Modes:**
- **Linear** = `excess_or_shortfall × penalty_rate` (proportional to violation severity)
- **Flat** = `penalty_rate` applied once if violated (binary pass/fail)

---

## 🏗️ Phase 03: The Three Giants (6 Rules)

| ID        | Group          | Rule Type           | Target              | Threshold | Penalty          | Condition                   |
| :-------- | :------------- | :------------------ | :------------------ | :-------- | :--------------- | :-------------------------- |
| **PB-01** | Power Block    | `center_proximity`  | Plot Center         | 20 m      | 100 pts / m      | Only on excess beyond 20 m  |
| **PB-02** | Power Block    | `boundary_setback`  | Primary Road        | 5 m       | 5000 pts (flat)  | If any edge < 5 m           |
| **CT-01** | Cooling Tower  | `leeward_edge`      | Wind Direction      | 30 m      | 1000 pts (flat)  | Must be on **downwind** edge |
| **CT-02** | Cooling Tower  | `min_distance`      | Admin Building      | 50 m      | 500 pts / m      | If distance < 50 m          |
| **AD-01** | Admin Building | `boundary_setback`  | Primary Road        | 20 m      | 1000 pts (flat)  | If any edge < 20 m          |
| **AD-02** | Admin Building | `max_distance`      | Gate House          | 50 m      | 100 pts / m      | If distance > 50 m          |
| **AD-03** | Admin Building | `windward_edge`     | Wind Direction      | 30 m      | 1000 pts (flat)  | Must be on **upwind** edge   |

---

## 🔧 Phase 04: New Groups (Expanded Rules)

### New Rectangle Groups

| ID        | Group          | Rule Type           | Target              | Threshold | Penalty          | Condition                   |
| :-------- | :------------- | :------------------ | :------------------ | :-------- | :--------------- | :-------------------------- |
| **GH-01** | Gate House     | `boundary_setback`  | Primary Road        | 0 m       | 5000 pts (flat)  | Must be on site boundary    |
| **CT-03** | Cable Tunnel   | `min_distance`      | Power Block         | 5 m       | 500 pts / m      | Must be near Power Block    |
| **CT-04** | Cable Tunnel   | `max_distance`      | Power Block         | 30 m      | 200 pts / m      | Cannot be too far from PB   |
| **LP-01** | LPG/Metering   | `boundary_setback`  | Primary Road        | 10 m      | 1000 pts (flat)  | Setback from boundary       |
| **LP-02** | LPG/Metering   | `min_distance`      | Power Block         | 30 m      | 300 pts / m      | Safe distance from PB       |
| **FL-01** | Flare          | `leeward_edge`      | Wind Direction      | 30 m      | 1000 pts (flat)  | Must be on **downwind** edge |
| **FL-02** | Flare          | `min_distance`      | Admin Building      | 100 m     | 500 pts / m      | Safe distance from Admin    |
| **FL-03** | Flare          | `min_distance`      | Power Block         | 50 m      | 300 pts / m      | Safe distance from PB       |
| **WW-01** | WT/WWT         | `boundary_setback`  | Primary Road        | 10 m      | 1000 pts (flat)  | Setback from boundary       |
| **WW-02** | WT/WWT         | `leeward_edge`      | Wind Direction      | 50 m      | 500 pts (flat)   | Must be on **downwind** edge |
| **WA-01** | Water          | `boundary_setback`  | Primary Road        | 10 m      | 1000 pts (flat)  | Setback from boundary       |
| **WA-02** | Water          | `min_distance`      | WT/WWT              | 10 m      | 200 pts / m      | Near water treatment        |
| **WA-03** | Water          | `max_distance`      | WT/WWT              | 80 m      | 100 pts / m      | Cannot be too far from WWT  |

### Polyline Racks

Rack physical widths: Pipe Rack = 6 m, Main Rack = 8 m, Utility Rack = 6 m.

> **Rack connection rules (TBD):** Once building-to-rack connections are defined, 
> `pipe_rack_proximity` rules will be added here. All rack rules will enforce 
> "minimum distance as possible" between the rack line and its connected buildings.

---

*To add a new rule: add a row to this table, then add a matching dict to the `RULES` list in `Core/Rules.py`.*

---

## Pending Info From User

- [ ] **1) Building sizes** — confirm or update dimensions for each group
- [ ] **2) Rack connections** — which buildings does each rack connect? (e.g., Pipe Rack: Power Block <-> Cooling Tower)
- [ ] **3) Placement priority** — ordered list of buildings by importance (placed first = highest priority)
- [ ] **4) Manual placement list** — buildings that the user places manually (not auto-generated)

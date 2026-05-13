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
| `rack_length`         | `_eval_rack_length()`       | Edge-to-edge distance between two connected buildings | Linear     |
| `pipe_rack_proximity` | `_eval_pipe_rack_proximity()` | Distance from building edge to nearest rack line | Linear       |
| `road_proximity`      | `_eval_road_proximity()`    | Distance from building/rack to nearest road      | Linear       |
| `boundary_overflow`   | `_eval_boundary_overflow()` | Penalty for buildings exceeding site boundaries   | Logarithmic  |

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

## 📐 Building Dimensions & Constraints (mm)

| Building/Block | Dimensions (W x L) | Notes |
| :--- | :--- | :--- |
| **Power Block** | 150,000 x 150,000 | Site Center Anchor |
| **Cooling Tower** | 40,000 x 183,000 | Includes aux equipment from Excel |
| **Admin Building** | 30,000 x 25,000 | Include parking area |
| **Gate House** | 12,000 x 12,000 | Include parking; North Center |
| **GIS** | 110,000 x 51,000 | North-East position |
| **Flare** | Ø 40,000 | Flare Stack only (KO Drum separate) |
| **WT/WWT** | 81,000 x 56,000 | Includes aux equipment from Excel |
| **Warehouse** | 59,000 x 40,000 | Include parking area |
| **Water Block** | 37,000 (RAW) / 10,000 (Demi) | Various tanks inside |

---

## 🛣️ Phase 05: Infrastructure & Connectivity

### Infrastructure Constraints
- **Road Width:** 7,000 mm (all roads)
- **Perimeter Fire Road:** Edge must be 5,000 mm from Site Boundary.
- **Road-to-Building:** Min. 3,000 mm distance.
- **Road-to-Rack:** Min. 2,000 mm distance.
- **Rack-to-Block:** Min. 2,500 mm distance.
- **Pipe Rack Width:** 6,000 mm or 2,000 mm (as per Excel).

### Placement Priorities & Logic

Buildings are placed sequentially in the order below. Each step uses `_try_place_collision_aware` with 50–100 retries; if a step fails the entire candidate is discarded. **Earlier = more layout influence.**

| #   | Building           | Position Rule                                                | Rotation              | Rationale                                                          |
| :-: | :----------------- | :----------------------------------------------------------- | :-------------------- | :----------------------------------------------------------------- |
| 1   | **Gate House**     | **FIXED** — N-center, flush with top boundary                | Fixed (square)        | Anchors site entrance (rule GH-01: must sit on site edge)          |
| 2   | **GIS**            | **FIXED** — NE corner, 15 m from boundary                    | Fixed                 | Pinned to grid-tie corner so cable tunnel to PB is short           |
| 3   | **Power Block**    | Site center, ±5 % jitter                                     | None (square 150×150) | Heart of plant — minimizes total rack distance to every utility    |
| 4   | **Admin Building** | North zone between GH and PB (d_GH ≤ 80 m, d_PB ≤ 120 m)     | Random 90°            | Near gate for human entry, near PB for operations                  |
| 5   | **Cooling Tower**  | Leeward edge (opposite wind dir), depth 15–30 m              | Random 90°            | Plumes must blow away from site                                    |
| 6   | **WT/WWT**         | Leeward third of site, ≥ 15 m setback                        | Random 90°            | Odors stay downwind                                                |
| 7   | **Water**          | Adjacent to WT/WWT (right/left/top/bottom), no overlap       | None (square)         | Hydraulically tied to WT/WWT                                       |
| 8   | **Flare**          | Leeward corner, 15–30 m depth                                | None (square)         | Heat radiation away from buildings                                 |
| 9   | **LPG/Metering**   | Random corner, ≥ 15 m setback                                | Random 90°            | Hazardous-area separation                                          |
| 10  | **Warehouse**      | Any remaining gap, ≥ 5 m clear of all placed buildings       | Random 90°            | Lowest priority — fills leftover space                             |

**Three tiers:**
- **Pinned anchors (1–2)** — code-driven fixtures, always succeed, rotation fixed.
- **Heart + connections (3–4)** — Power Block centers the layout; Admin keys off both fixed and central anchors.
- **Wind-sensitive (5–8) and hazardous (9)** — placed via wind direction + corner heuristics. Warehouse (10) absorbs slack.

**Rotation:** non-square, non-fixed buildings randomly take 0° or 90°. Square footprints (PB, Water, Flare, GH) and pinned buildings (GH, GIS) are never rotated.

**Racks** (placed after all buildings): Power Block must connect to Cooling Tower, LPG/Metering, and WT/WWT via Pipe Rack; to Admin via Main Rack; WT/WWT connects to Water and Cooling Tower via Utility Rack; GIS connects to Power Block via Cable Tunnel.

---

## 🔧 Phase 04 & 05: Expanded Rules (30 Total)

### New Rectangle Groups

| ID        | Group          | Rule Type           | Target              | Threshold | Penalty          | Condition                   |
| :-------- | :------------- | :------------------ | :------------------ | :-------- | :--------------- | :-------------------------- |
| **GH-01** | Gate House     | `boundary_setback`  | Primary Road        | 0 m       | 5000 pts (flat)  | Must be on site boundary    |
| **GIS-01** | GIS            | `boundary_setback`  | Primary Road        | 15 m      | 1000 pts (flat)  | Setback from boundary       |
| **WH-01** | Warehouse      | `boundary_setback`  | Primary Road        | 15 m      | 1000 pts (flat)  | Setback from boundary       |
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

### Infrastructure (Road) Rules

| ID        | Group          | Rule Type           | Target              | Threshold | Penalty          | Condition                   |
| :-------- | :------------- | :------------------ | :------------------ | :-------- | :--------------- | :-------------------------- |
| **RD-01** | Power Block    | `road_proximity`    | Perimeter Road      | 3 m       | 500 pts / m      | Gap between building & road |
| **RD-02** | Cooling Tower  | `road_proximity`    | Perimeter Road      | 3 m       | 500 pts / m      | Gap between building & road |
| **RD-03** | Admin Building | `road_proximity`    | Perimeter Road      | 3 m       | 500 pts / m      | Gap between building & road |

### Polyline Racks — Connection Map

Racks are pipe/cable corridors connecting buildings. **Shorter = better.**

| Rack | Width | Purpose | Connects |
| :--- | :---- | :------ | :------- |
| **Pipe Rack** | 6 m | Process piping (cooling water, fuel gas, steam/condensate) | Power Block ↔ Cooling Tower, Power Block ↔ LPG/Metering, Power Block ↔ WT/WWT |
| **Main Rack** | 8 m | Electrical cables + control signals | Power Block ↔ Admin Building |
| **Utility Rack** | 6 m | Utility services (raw water, fire water, makeup water) | WT/WWT ↔ Water, WT/WWT ↔ Cooling Tower |
| **Cable Tunnel** | 3 m | Underground cable route | GIS ↔ Power Block |

### Rack Length Rules

Rule: each connection should be as short as possible. Penalty = `rack_length × penalty_rate`.

| ID        | Rack           | Rule Type      | Building A       | Building B       | Penalty          | Condition                      |
| :-------- | :------------- | :------------- | :--------------- | :--------------- | :--------------- | :----------------------------- |
| **PR-01** | Pipe Rack      | `rack_length`  | Power Block      | Cooling Tower    | 50 pts / m       | Shorter = better (cooling water) |
| **PR-02** | Pipe Rack      | `rack_length`  | Power Block      | LPG/Metering     | 30 pts / m       | Shorter = better (fuel gas)    |
| **PR-03** | Pipe Rack      | `rack_length`  | Power Block      | WT/WWT           | 30 pts / m       | Shorter = better (demin water) |
| **MR-02** | Main Rack      | `rack_length`  | Power Block      | Admin Building   | 20 pts / m       | Shorter = better (control cables) |
| **UR-01** | Utility Rack   | `rack_length`  | WT/WWT           | Water            | 40 pts / m       | Shorter = better (raw water)   |
| **UR-02** | Utility Rack   | `rack_length`  | WT/WWT           | Cooling Tower    | 30 pts / m       | Shorter = better (makeup water) |
| **CT-03** | Cable Tunnel   | `rack_length`  | GIS              | Power Block      | 20 pts / m       | Shorter = better (high voltage) |

---

*To add a new rule: add a row to this table, then add a matching dict to the `RULES` list in `Core/Rules.py`.*

---

## Pending Info From User

- [x] **1) Building sizes** — Dimensions updated for 10 main groups.
- [x] **2) Rack connections** — Defined: PB to WT/WWT/Water.
- [x] **3) Placement priority** — Ordered: GH(N-Center), PB(Center), Admin(Near GH/PB), GIS(NE).
- [ ] **4) Excel-based equipment list** — Need to integrate specific aux equipment dimensions from Excel for CT/WWT.

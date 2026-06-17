# ⚖️ Rule Engine: Penalty Scoring Logic

This document is the **Single Source of Truth** for all layout rules.
The generative design system evaluates layouts by calculating a **Total Penalty Score**. 
*Lower score = Better layout.* 
A score of `0` means a perfect layout with no rule violations.

## 📖 Available Rule Types

Each rule has a **Rule Type** that maps to a generic evaluator function in `Rules.py`.

| Rule Type             | Function in Rules.py          | What it checks                                        | Penalty Mode |
| :-------------------- | :---------------------------- | :---------------------------------------------------- | :----------- |
| `center_proximity`    | `_eval_center_proximity()`    | Distance from building center to plot center          | Linear       |
| `boundary_setback`    | `_eval_boundary_setback()`    | Min distance from any edge to site boundary           | Flat         |
| `windward_edge`       | `_eval_windward_edge()`       | Is building on the windward side of the plot?         | Flat         |
| `min_distance`        | `_eval_min_distance()`        | Center-to-center distance must be ≥ threshold         | Linear       |
| `max_distance`        | `_eval_max_distance()`        | Center-to-center distance must be ≤ threshold         | Linear       |
| `leeward_edge`        | `_eval_leeward_edge()`        | Is building on the downwind (leeward) side?           | Flat         |
| `rack_length`         | `_eval_rack_length()`         | Edge-to-edge distance between two connected buildings | Linear       |
| `pipe_rack_proximity` | `_eval_pipe_rack_proximity()` | Distance from building edge to nearest rack line      | Linear       |
| `road_proximity`      | `_eval_road_proximity()`      | Distance from building/rack to nearest road           | Linear       |
| `boundary_overflow`   | `_eval_boundary_overflow()`   | Penalty for buildings exceeding site boundaries       | Logarithmic  |

**Penalty Modes:**
- **Linear** = `excess_or_shortfall × penalty_rate` (proportional to violation severity)
- **Flat** = `penalty_rate` applied once if violated (binary pass/fail)

---

## 🏗️ Phase 03: The Three Giants (6 Rules)

| ID        | Group          | Rule Type           | Target         | Threshold | Penalty         | Condition                    |
| :-------- | :------------- | :------------------ | :------------- | :-------- | :-------------- | :--------------------------- |
| **PB-01** | Power Block    | `center_proximity`  | Plot Center    | 20 m      | 100 pts / m     | Only on excess beyond 20 m   |
| **PB-02** | Power Block    | `boundary_setback`  | Primary Road   | 5 m       | 5000 pts (flat) | If any edge < 5 m            |
| **CT-01** | Cooling Tower  | `leeward_edge`      | Wind Direction | 120 m     | 1000 pts (flat) | Must be on **downwind** edge |
| **CT-02** | Cooling Tower  | `min_distance`      | Admin Building | 50 m      | 500 pts / m     | If distance < 50 m           |
| **AD-01** | Admin Building | `boundary_setback`  | Primary Road   | 20 m      | 1000 pts (flat) | If any edge < 20 m           |
| **AD-02** | Admin Building | `max_gate_distance` | Site Gate      | 80 m      | 100 pts / m     | If distance > 80 m           |
| **AD-03** | Admin Building | `windward_edge`     | Wind Direction | 30 m      | 1000 pts (flat) | Must be on **upwind** edge   |

---

## 📐 Building Dimensions & Constraints (mm)

| Building/Block | Dimensions (W x L) | Notes |
| :--- | :--- | :--- |
| **Power Block** | 150,000 x 150,000 | Site Center Anchor |
| **Cooling Tower** | 40,000 x 183,000 | Strict building footprint |
| **Admin Building** | 30,000 x 25,000 | Strict building footprint (no parking padding) |
| **Gate House** | 12,000 x 12,000 | Strict building footprint (no parking padding) |
| **GIS** | 110,000 x 51,000 | North-East position |
| **Flare** | Ø 40,000 | Flare Stack only (KO Drum separate) |
| **WT/WWT** | 81,000 x 56,000 | Strict building footprint |
| **Warehouse** | 59,000 x 40,000 | Strict building footprint (no parking padding) |
| **RAW Water Tank** | Ø 37,000 | RAW Water Tank circle |
| **Demi Water Tank**| 25,000 x 12,000 | (x2) Ø10 Demi Tanks side-by-side |

---

## 🛣️ Phase 05: Infrastructure & Connectivity

### Infrastructure Constraints
- **Primary Road Width:** 8,000 mm 
- **Secondary Road Width:** 6,000 mm
- **Access Road Width:** 6000 mm
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
| 3   | **RAW Water Tank** | **FIXED** — User-defined edge and ratio                      | None (square)         | Hydraulically tied to WT/WWT, fixed anchor                         |
| 4   | **Power Block**    | Site center, ±5 % jitter                                     | None (square 150×150) | Heart of plant — minimizes total rack distance to every utility    |
| 5   | **Cooling Tower**  | Leeward edge, closest to Power Block                         | Random 90°            | Plumes must blow away from site, compact placement                 |
| 6   | **WT/WWT**         | Near RAW water tank, closest to Power Block                  | Random 90°            | Odors stay downwind, compact placement                             |
| 7   | **Warehouse**      | Any remaining gap, closest to Power Block                    | Random 90°            | Fills leftover space compactly                                     |
| 8   | **Flare**          | Leeward corner, closest to Power Block                       | None (square)         | Heat radiation away from buildings, compact placement              |
| 9   | **Admin Building** | Closest to Site Gate and Power Block                         | Random 90°            | Near gate for human entry, near PB for operations                  |
| 10  | **Demi Water Tank**| Near RAW Water Tank                                          | Random 90°            | Hydraulically tied to RAW Water Tank                               |

**Three tiers:**
- **Pinned anchors (1–3)** — code-driven fixtures, always succeed, rotation fixed.
- **Heart (4)** — Power Block centers the layout.
- **Priority by footprint size (5–10)** — Placed in descending order of size, each optimized to be as close to the Power Block as possible, maximizing compactness while respecting all boundaries and specific zone constraints.

**Rotation:** non-square, non-fixed buildings randomly take 0° or 90°. Square footprints (PB, RAW Water Tank, Flare, GH) and pinned buildings (GH, GIS) are never rotated.

**Racks** (placed after all buildings, before roads in Phase 06): single 6m-wide Pipe Rack connects PB↔Cooling Tower, PB↔WT/WWT, WT/WWT↔RAW Water Tank, WT/WWT↔Cooling Tower, RAW Water Tank↔Demi Water Tank. GIS↔PB is a separate cable tunnel (not a rack).

---

## 🔧 Phase 04 & 05: Expanded Rules (30 Total)

### New Rectangle Groups

| ID        | Group          | Rule Type           | Target              | Threshold | Penalty          | Condition                   |
| :-------- | :------------- | :------------------ | :------------------ | :-------- | :--------------- | :-------------------------- |
| **GH-01** | Gate House     | `boundary_setback`  | Primary Road        | 0 m       | 5000 pts (flat)  | Must be on site boundary    |
| **GIS-01**| GIS            | `boundary_setback`  | Primary Road        | 15 m      | 1000 pts (flat)  | Setback from boundary       |
| **WH-01** | Warehouse      | `boundary_setback`  | Primary Road        | 15 m      | 1000 pts (flat)  | Setback from boundary       |
| **WH-02** | Warehouse      | `max_distance`      | Power Block         | 250 m     | 100 pts / m      | Compact layout              |
| **FL-01** | Flare          | `leeward_edge`      | Wind Direction      | 30 m      | 1000 pts (flat)  | Must be on **downwind** edge |
| **FL-02** | Flare          | `min_distance`      | Admin Building      | 100 m     | 500 pts / m      | Safe distance from Admin    |
| **FL-03** | Flare          | `min_distance`      | Power Block         | 50 m      | 300 pts / m      | Safe distance from PB       |
| **FL-04** | Flare          | `max_distance`      | Power Block         | 150 m     | 100 pts / m      | Compact layout              |
| **WW-01** | WT/WWT         | `boundary_setback`  | Primary Road        | 10 m      | 1000 pts (flat)  | Setback from boundary       |
| **WW-02** | WT/WWT         | `leeward_edge`      | Wind Direction      | 50 m      | 500 pts (flat)   | Must be on **downwind** edge |
| **WW-03** | WT/WWT         | `max_distance`      | Power Block         | 200 m     | 100 pts / m      | Compact layout              |
| **WA-01** | RAW Water Tank | `boundary_setback`  | Primary Road        | 10 m      | 1000 pts (flat)  | Setback from boundary       |
| **WA-02** | RAW Water Tank | `min_distance`      | WT/WWT              | 10 m      | 200 pts / m      | Near water treatment        |
| **WA-03** | RAW Water Tank | `max_distance`      | WT/WWT              | 80 m      | 100 pts / m      | Cannot be too far from WWT  |
| **CT-04** | Cooling Tower  | `max_distance`      | Power Block         | 180 m     | 100 pts / m      | Compact layout              |
| **AD-04** | Admin Building | `max_distance`      | Power Block         | 150 m     | 100 pts / m      | Compact layout              |
| **DW-02** | Demi Water Tank| `max_distance`      | RAW Water Tank      | 40 m      | 100 pts / m      | Near RAW Water              |

### Infrastructure (Road) Rules

| ID        | Group          | Rule Type           | Target              | Threshold | Penalty          | Condition                   |
| :-------- | :------------- | :------------------ | :------------------ | :-------- | :--------------- | :-------------------------- |
| **RD-01** | Power Block    | `road_proximity`    | Perimeter Road      | 3 m       | 500 pts / m      | Gap between building & road |
| **RD-02** | Cooling Tower  | `road_proximity`    | Perimeter Road      | 3 m       | 500 pts / m      | Gap between building & road |
| **RD-03** | Admin Building | `road_proximity`    | Perimeter Road      | 3 m       | 500 pts / m      | Gap between building & road |

### Polyline Racks — Connection Map

Racks are pipe corridors connecting process blocks. **Shorter = better.**

Phase 06: a single rack type with **width 6 m** carries all process connections (cooling water, steam/condensate, demin water, raw water, makeup water). Five blocks need racks: **Power Block, Cooling Tower, WT/WWT, RAW Water Tank, Demi Water Tank.**

| Rack | Width | Connects |
| :--- | :---- | :------- |
| **Pipe Rack** | 6 m | PB ↔ Cooling Tower, PB ↔ WT/WWT, WT/WWT ↔ RAW Water Tank, WT/WWT ↔ Cooling Tower, RAW Water Tank ↔ Demi Water Tank |

**Cable Tunnel (GIS ↔ PB)** is *not* a rack — it's an underground cable route handled by separate logic (not part of Step 1.2 rack placement).

**Admin Building** does not get a rack — control cables go via the cable tunnel route, not a pipe rack.

### Rack Length Rules

Rule: each connection should be as short as possible. Penalty = `rack_length × penalty_rate`.

| ID        | Rack           | Rule Type      | Building A       | Building B       | Penalty          | Condition                      |
| :-------- | :------------- | :------------- | :--------------- | :--------------- | :--------------- | :----------------------------- |
| **PR-01** | Pipe Rack      | `rack_length`  | Power Block      | Cooling Tower    | 50 pts / m       | Shorter = better (cooling water) |
| **PR-03** | Pipe Rack      | `rack_length`  | Power Block      | WT/WWT           | 30 pts / m       | Shorter = better (demin water) |
| **UR-01** | Pipe Rack      | `rack_length`  | WT/WWT           | RAW Water Tank   | 40 pts / m       | Shorter = better (raw water)   |
| **UR-02** | Pipe Rack      | `rack_length`  | WT/WWT           | Cooling Tower    | 30 pts / m       | Shorter = better (makeup water) |
| **CT-03** | Cable Tunnel   | `rack_length`  | GIS              | Power Block      | 20 pts / m       | Separate logic (not Step 1.2)  |

---

*To add a new rule: add a row to this table, then add a matching dict to the `RULES` list in `Core/Rules.py`.*

---

## Pending Info From User

- [x] **1) Building sizes** — Dimensions updated for 10 main groups.
- [x] **2) Rack connections** — Defined: PB to WT/WWT/Water.
- [x] **3) Placement priority** — Ordered: GH(N-Center), PB(Center), Admin(Near GH/PB), GIS(NE).
- [ ] **4) Excel-based equipment list** — Need to integrate specific aux equipment dimensions from Excel for CT/WWT.

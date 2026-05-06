


### Phase_01: The Empty Plot.
#### Step_01: Make Dashboard

"Create a **Streamlit** dashboard application titled '**PowerPlan AI: Layout Generator**'.

**Requirements:**

1. **Page Config**: Set the layout to 'wide'.
2. **Header**: Include a main title with an emoji '⚡ PowerPlan AI: Layout Generator' and a sub-header '### Phase_01: Site Boundary & Primary Road Setback'.
3. **Sidebar Controls**: Create two sliders in the sidebar for 'Plot Width (A)' and 'Plot Length (B)' with a range from 100 to 1000 and a default value of 400 and 300 respectively.
4. **Core Visualization**:
    - Use **Matplotlib** to render a 2D geometry plot.
    - **Site Boundary**: Draw a solid black rectangle based on the slider inputs with a light blue fill color (#f0f8ff).
    - **Road Setback**: Implement a logic to draw a red dashed line rectangle representing a 5m internal setback from all sides of the boundary.
    - **Scaling**: Ensure the plot maintains an 'equal' aspect ratio and includes a small margin (padding) around the site boundary so it's not touching the edges of the plot.
5. **Style**: Use clean, professional English comments and labels throughout the code."




### Phase_02: The Three Giants
#### Step_01: Define and Render the Building Clusters

"Update the **PowerPlan AI** application to introduce the first 3 major building clusters: Power Block, Cooling Tower, and Admin Building.

**Requirements:**

1. **Core Engine Logic (`Core/Groups.py`)**:
    - Create a new module to define the groups as data dictionaries (name, x, y, width, height, color).
    - Calculate their default starting positions based on the site size:
        - **Power Block**: Center of the plot (Size: 120x80, Color: #4a90d9).
        - **Cooling Tower**: Right edge of the plot (Size: 60x80, Color: #7ed6a0).
        - **Admin Building**: Lower-left corner (Size: 50x40, Color: #f5a623).
    - Create a `draw_group(ax, group)` function that strictly uses explicit coordinate lists (`ax.plot()` and `ax.fill()`) instead of matplotlib patches, ensuring the geometry is future-ready for CAD line export.
2. **Dashboard UI (`Dashboard/App.py`)**:
    - Import the groups and render them inside the existing Matplotlib layout.
    - Add a new sidebar section 'Manual Group Offsets (m)'.
    - Create X and Y sliders (-200 to 200) for each of the 3 groups so the user can manually shift their positions to test the canvas limits.
3. **Architecture Rules**:
    - Keep strict separation of concerns: UI code stays in Dashboard, geometry data and logic stay in Core.
    - Ensure all python files use Capitalized naming conventions (`App.py`, `Groups.py`)."

---

### Phase_03: Engineering Rules (The Logic)
#### Step_01: Rules Engine + Visual RED Alerts

"Implement **Phase 3** of the PowerPlan AI system: a live penalty-scoring rule engine with visual violation alerts.

**Core Engine (`Core/Rules.py`)**:
- Implement 6 rules as individual Python functions, each returning a standardized dict: `{id, name, group, passed, penalty, measured, threshold, calc}`.
- Rules (from `!Scoring_Logic.md`):
  - **PB-01**: Power Block center within ±20 m tolerance of plot center. Beyond tolerance: 100 pts/m excess.
  - **PB-02**: Power Block must not violate 5 m primary road setback on any side. 5,000 pts flat if violated.
  - **CT-01**: Cooling Tower must be within 30 m of the windward edge (direction from Wind selectbox). 1,000 pts flat if not.
  - **CT-02**: Cooling Tower center ≥ 50 m from Admin Building center. 500 pts/m shortfall.
  - **AD-01**: Admin Building must be ≥ 20 m from any site boundary. 1,000 pts flat if violated.
  - **AD-02**: Admin Building center ≤ 50 m from Gate House at `(site_width/2, 0)`. 100 pts/m excess.
- `evaluate_all(groups, site_width, site_length, wind_dir)` returns `{results, total_penalty, violations_by_group}`.
- Zero Streamlit imports in Core.

**Dashboard (`Dashboard/app.py`)**:
- After drawing buildings, call `evaluate_all()` and draw a **crimson dashed border** overlay on each violating building, plus a small `⚠ rule-id` badge above it.
- Below the plot: 3 `st.metric` cards (Total Penalty / Rules Passing / Rules Failing).
- Per-rule detail: `st.expander` for each rule — **auto-expanded if failing** — showing 3 columns: 📐 Measured | 🎯 Threshold | 🧮 Calculation.

**Visuals on the plot**:
- Draw **dashed distance lines** between all 3 building center pairs (PB↔CT, PB↔Admin, CT↔Admin) with distance labels in meters. CT↔Admin line is red if < 50 m.
- Draw **double-headed setback arrows** from each building's nearest edge to the site boundary, labeled with the distance. Color green if passing, red if failing.
  - Power Block: threshold 5 m.
  - Cooling Tower: arrow points toward **windward edge** specifically (wind-aware). Threshold 30 m.
  - Admin Building: threshold 20 m.
- Draw **Gate House** as a 12×8 m dark brown rectangle straddling the bottom boundary at `(site_width/2, 0)`.
- Show **auto-computed scale** (e.g., 'Scale 1/250') in the top-right corner, snapped to standard values: 1:50, 1:100, 1:200, 1:250, 1:500, 1:1000, 1:2000."

#### Step_02: Generative Layout Engine

"Implement **Phase 3 Step 2** of the PowerPlan AI system: a constrained generative layout engine replacing manual sliders.

**Core Engine (`Core/Main.py`)**:
- Implement `generate_layouts(site_width, site_length, wind_dir, n_results, min_rules_passing)`.
- Use **constrained random placement**:
  - **Power Block**: randomly placed near the plot center with ±25% variation, clamped to 5 m setback.
  - **Cooling Tower**: constrained to the windward zone (5–25 m from the windward edge), varying along the perpendicular axis.
  - **Admin Building**: randomly placed with ≥ 20 m setback AND center within 50 m of Gate House `(site_width/2, 0)`. 400 attempts max, fallback to bottom-center.
- Score each candidate with `evaluate_all()`. Only keep candidates with `passing_rules >= min_rules_passing`.
- Apply a **diversity filter**: reject a candidate if all 3 building positions are within 10 m of any already-accepted result.
- Sort final results by `total_penalty` ascending and return top `n_results`.

**Dashboard (`Dashboard/app.py`)** — full rewrite:
- Remove all manual position sliders.
- Sidebar: site width/length sliders, wind direction, number of layouts to generate (5–20), min rules passing (1–6).
- Centered **🎲 Generate Layouts** primary button.
- On click: call `generate_layouts()` with spinner, store results in `st.session_state`.
- Display results in a **5-column grid** of compact thumbnail plots (each showing: boundary, setback, gate house, wind indicator, buildings, violation overlays, inter-building distance lines).
- Summary metrics above grid: Best Score / Worst Score / Layouts Found.
- Below grid: **🔍 Detailed Rule Breakdown** — `st.selectbox` to pick any layout by rank → shows full `st.expander` rule breakdown (Measured / Threshold / Calculation) for all 6 rules."

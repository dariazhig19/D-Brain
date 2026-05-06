
# 🚀 Product Vision: PowerPlan AI (Layout_Gen_Design)

**Project Goal:**

Automate the generation of power plant Plot Plans. Develop a system to optimize the placement of 60+ buildings on a site based on engineering constraints and rules.

## 🛠 Tech Stack (Vibe Coding)

- **Architect (Organization):** Obsidian
- **Engine (IDE):** VS Code + Antigravity extension
- **Draftsman (Visualization):** Matplotlib (Python library)
- **Interface (Dashboard):** Streamlit (Web UI)
- **Language:** Python


## 🎯 Key Features

1. **Interactive Site Setup:** Define plot boundaries (a × b) using sliders in the Dashboard.
2. **Smart Grouping:** Place major clusters (Power Block, Cooling Tower, Admin) according to rules.
3. **Automated Scoring:** Real-time validation of distances (e.g., "Admin must be 50m away from Cooling Tower").
4. **Generative Layouts:** Run multiple iterations to find the optimal arrangement with the highest score.


## 📈 Development Roadmap (Phased Plan)

### Phase_01: The Empty Plot (Completed)

- [x] Initialize project structure: `Core/`, `Dashboard/`, `Data/`, `Notes/`.
- [x] Setup `Dashboard/App.py` using Streamlit.
- [x] Draw the site boundary (Rectangle) based on User Inputs.

### Phase_02: The Three Giants (Completed)

- [x] Define 3 main groups: **Power Block**, **Cooling Tower**, **Admin Building**.
- [x] Render them as colored blocks inside the plot.
- [x] Add manual X/Y coordinate sliders to test the canvas limits.

### Phase_03: Engineering Rules (Completed)

- [x] Translate Excel rules into Python functions in `Core/Rules.py`.
- [x] Implement distance checks (Setbacks from boundaries and between buildings).
- [x] Visual Alerts: Turn blocks **RED** if they violate a rule.

### Phase_04: Excel Integration & Sub-Clusters

- [ ] Parsing the Excel Data (`Plot plan requirement.xlsx`).
- [ ] Automated Rule Parsing (generating validation logic directly from Excel rules).
- [ ] Deconstruct the "Three Giants" into their individual sub-buildings (e.g., specific structures inside the Power Block).
- [ ] Introduce routing and placement rules for **Pipe Racks**.

### Phase_05: Generative Optimization

- [ ] Implementation of a scoring engine to evaluate "The Best Placement".
- [ ] Export final geometry to DXF/CAD format.

## 📍 Current Status: **Phase_04 (Excel Integration)**

# ⚖️ Rule Engine: Penalty Scoring Logic

This document is the **Single Source of Truth** for all layout rules.
The generative design system evaluates layouts by calculating a **Total Penalty Score**. 
*Lower score = Better layout.* 
A score of `0` means a perfect layout with no rule violations.

## 🏗️ Phase 2: The Three Giants

The following table defines the placement rules for the 3 main groups.
You can adjust the "Penalty per Unit" to make rules more or less strict.

| ID | Group | Constraint | Target Reference | Penalty per Unit | Condition |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **PB-01** | Power Block | Must be centered (±20 m tolerance) | Center of Plot | 100 pts / meter | Only on excess beyond 20 m |
| **PB-02** | Power Block | Minimum Setback | Primary Road | 5000 pts (Violation) | If distance < 5m |
| **CT-01** | Cooling Tower | Must be placed at | Windward Edge (Right) | 1000 pts | If not on edge |
| **CT-02** | Cooling Tower | Minimum Distance | Admin Building | 500 pts / meter | If distance < 50m |
| **AD-01** | Admin Building | Minimum Distance | Primary Road | 1000 pts | If distance < 20m |
| **AD-02** | Admin Building | Maximum Distance | Gate House | 100 pts / meter | If distance > 50m |

---

*Note: In Phase 4, a Python script will automatically parse this Markdown table to build the `Rules.py` logic!*

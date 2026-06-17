# Phase 2: The Three Giants — Implementation Plan

## Goal
Place 3 main building groups on the site plot using engineering rules from `Plot plan requirement.xlsx`.
Each group is a **rectangle** defined by X, Y position + width + height — the same concept as a Dynamo `Rectangle.ByCornerPoints`.

---

## How to Think About This (Dynamo → Python)

| Dynamo | Python equivalent |
|---|---|
| `Rectangle.ByCornerPoints(pt1, pt2)` | `ax.fill(x_list, y_list)` + `ax.plot(x_list, y_list)` |
| `Point.ByCoordinates(x, y)` | `(x, y)` — just a tuple |
| `Number Slider` | `st.sidebar.slider(...)` |
| `If / Watch` | `if / print` |
| `Group / List` | Python `dict` or `dataclass` |
| Node chain | Function call chain |

In Dynamo, nodes are **visual wires**. Here, wires = **function arguments**. The logic is identical — data flows from inputs → rules → geometry → canvas.

---

## Rules Extracted from Excel (`Layout` sheet)

### Group 1 — Power Block
> "Place at center. Road around perimeter. Connected to Pipe Rack."

| Rule | Translated constraint |
|---|---|
| Place at center | `x ≈ site_width/2`, `y ≈ site_length/2` |
| Road around perimeter | min 5m gap between Power Block edge and site boundary |
| Pipe Rack connected | Pipe Rack placed along Power Block edge (Phase 3+) |

**Members:** Gas Turbine Building, Steam Turbine Building, HRSG Building, Main Stack, Transformers (×3), CEMS, BFW Pump Area, Fire Fighting Buildings ×2, SCR Vaporizer

---

### Group 2 — Cooling Tower
> "Pipe Rack on block boundary. Place at windward side."

| Rule | Translated constraint |
|---|---|
| Windward side | Place at edge of site (large X or Y offset) |
| Pipe rack on boundary | CT block edge must be ≤ 6m from pipe rack axis |

**Members:** Cooling Tower, CW Pump Structure, CT Electrical Building, CT Chemical Injection House

---

### Group 3 — Admin Building
> "Place ≥ 20m from road, within 50m of gate. Gate within 100m. Distance from Cooling Tower ≥ 50m. Windward side."

| Rule | Translated constraint |
|---|---|
| ≥ 20m from road | `admin.y ≥ 20` (or from nearest road edge) |
| ≤ 50m from gate | `distance(admin, gate) ≤ 50` |
| Gate ≤ 100m | gate placed at site entrance |
| CT distance ≥ 50m | `distance(admin_center, ct_center) ≥ 50` |

**Members:** Administration Building, Gate House, Parking Area

---

## Data Model — How a Group is Represented

```python
# Each group = a plain dict (like a Dynamo custom node output)
{
    "name":   "Power Block",
    "x":      100,       # bottom-left corner X (meters)
    "y":      80,        # bottom-left corner Y (meters)
    "width":  120,       # group footprint width (meters)
    "height": 80,        # group footprint height (meters)
    "color":  "#4a90d9", # fill color for visualization
}
```

---

## File Structure for Phase 2

```
Layout_Gen_Design/
├── Core/
│   └── Groups.py       ← [NEW] Group definitions + placement logic
├── Dashboard/
│   └── App.py          ← [MODIFY] Import groups, draw them, add sliders
└── Data/
    └── Plot plan requirement.xlsx
```

**Rule:** `App.py` only draws. All logic (positions, sizes, rules) lives in `Core/Groups.py`.
This is equivalent to Dynamo's separation of "Geometry nodes" vs "Logic nodes."

---

## Step-by-Step Build Sequence

### Step 1 — `Core/Groups.py`: Define the 3 groups as data

Create a function `get_groups(site_width, site_height)` that returns a list of group dicts.
Positions are **calculated from site size** — not hardcoded.

```python
def get_groups(site_width, site_height):
    pw_w, pw_h = 120, 80   # Power Block footprint
    ct_w, ct_h = 60,  80   # Cooling Tower footprint
    adm_w, adm_h = 50, 40  # Admin footprint

    return [
        {   # Power Block — centered on site
            "name": "Power Block",
            "x": (site_width - pw_w) / 2,
            "y": (site_height - pw_h) / 2,
            "width": pw_w, "height": pw_h,
            "color": "#4a90d9",
        },
        {   # Cooling Tower — right edge, vertically centered
            "name": "Cooling Tower",
            "x": site_width - ct_w - 10,
            "y": (site_height - ct_h) / 2,
            "width": ct_w, "height": ct_h,
            "color": "#7ed6a0",
        },
        {   # Admin Building — lower-left, near gate
            "name": "Admin Building",
            "x": 20,
            "y": 20,
            "width": adm_w, "height": adm_h,
            "color": "#f5a623",
        },
    ]
```

---

### Step 2 — `Core/Groups.py`: Draw function (geometry output)

```python
def draw_group(ax, group):
    x, y, w, h = group["x"], group["y"], group["width"], group["height"]
    gx = [x,   x+w, x+w, x,   x]   # 5-point closed contour (same as site boundary)
    gy = [y,   y,   y+h, y+h, y]
    ax.fill(gx, gy, color=group["color"], alpha=0.5, zorder=1)
    ax.plot(gx, gy, color="black", linewidth=0.8, zorder=2)
    ax.text(x + w/2, y + h/2, group["name"],
            ha='center', va='center', fontsize=7, fontweight='bold')
```

---

### Step 3 — `App.py`: Import and call

```python
from Core.Groups import get_groups, draw_group

groups = get_groups(site_width, site_length)
for g in groups:
    draw_group(ax, g)
```

---

### Step 4 — Sidebar sliders for manual override (optional in Phase 2)

Sliders for X/Y offset per group — lets you test canvas limits manually before Phase 3 auto-placement.

```python
st.sidebar.subheader("Power Block Position")
pb_dx = st.sidebar.slider("PB offset X", -200, 200, 0, step=5)
pb_dy = st.sidebar.slider("PB offset Y", -200, 200, 0, step=5)
# then add dx/dy to the group's x/y before drawing
```

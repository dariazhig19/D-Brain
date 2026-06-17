# Footprint Refinement & Rendering Plan

## Goal
Update the layout engine to render specific components (Flare, RAW Water Tank) as true circles based on their diameters, split the generic "Water" block into individual `RAW Water Tank` and `Demi Water Tank` components, and completely remove the `LPG/Metering` group.

## Proposed Changes

### 1. Shape Definitions & Data (`Core/Groups.py`)
- Remove `LPG/Metering` and `Water` from `FOOTPRINTS` and `GROUP_COLORS`.
- Add `RAW Water Tank` as `(37, 37)`.
- Add `Demi Water Tank` as `(25, 12)` (to fit two Ø10m tanks side-by-side with minimal padding).
- Define a new dictionary `SHAPES` to explicitly identify round footprints:
  ```python
  SHAPES = {
      "Flare": "circle",
      "RAW Water Tank": "circle"
  } # Default fallback for everything else is "rectangle"
  ```

### 2. Dashboard UI & Rendering (`Dashboard/App.py`)
- **UI Update**: Rename the "Water Anchor" sliders in the sidebar to **"RAW Water Tank Anchor"**.
- **Rendering Update**: Modify the Matplotlib plotting loop. If `SHAPES.get(name) == "circle"`, use `plt.Circle` instead of `plt.Rectangle`. The radius will be `width / 2`. 

### 3. Placement Logic (`Core/Main.py`)
- **Anchor Logic**: Change the anchor placement from `Water` to `RAW Water Tank`.
- **Demi Water Tank**: Add a new placement function `_place_demi_water` that automatically attaches the Demi Water Tank directly adjacent to the RAW Water Tank.
- **WT/WWT Logic**: Update `_place_wt_wwt` to anchor itself to the `RAW Water Tank` instead of the old Water block.
- **LPG Removal**: Delete all references and placement logic for `LPG/Metering`.

### 4. Footprint & Buffer Tuning
- **Footprint Shrinkage (`Core/Groups.py`)**: Stripped out assumed parking and extra clearance padding from `FOOTPRINTS` to leave only the raw structural dimensions:
  - `Admin Building`: `30x25` (was `50x40`)
  - `Gate House`: `12x12` (was `20x20`)
  - `Warehouse`: `59x40` (was `90x55`)
  - `WT/WWT`: `81x56` (was `100x80`)
- **A* Pathfinder Calibration (`Core/Roads.py`)**: 
  - Adjusted the grid resolution (`cell_size=2.5m`) and activated morphological erosion (`width_cells=1`) to enforce a physical **7.5m road corridor footprint**.
  - Configured `ROAD_TO_BUILDING = 6` (enforcing a safe 7.5m buffer on the grid due to ceiling math).
- **Cooling Tower Generative Bounds (`Core/Main.py` & `Core/Rules.py`)**:
  - Expanded `_place_cooling_tower` boundary search zone from a strict 15m strip to the entire outer **40% of the downwind side**.
  - Increased `CT-01` (Leeward Edge) rule threshold from 30m to **120m** so the AI can freely place the Cooling Tower vertically inside the inland gap between WT/WWT and the Power Block without penalty.

## Open Questions
> [!IMPORTANT]
> The **Flare** is defined as `Ø40,000` (Stack only, KO Drum separate). If the footprint on the map is rendered as a perfect Ø40m circle, where do you want the KO Drum to go? Should the generative engine ignore the KO drum entirely, or do you want me to create a separate `Flare K.O Drum` block that the engine places next to the Flare?

## Verification Plan
1. Test generation to ensure `LPG/Metering` is gone.
2. Confirm `RAW Water Tank` and `Flare` render visually as circles in the Streamlit plot.
3. Check that WT/WWT and Demi Water Tanks correctly cluster around the user-placed RAW Water Tank.
4. Verify that internal roads successfully find 8m corridors without crashing the A* network.
5. Validate that the Cooling Tower correctly positions itself vertically inside the inland gap.

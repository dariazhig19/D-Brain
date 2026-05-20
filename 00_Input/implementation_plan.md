# Ring Road Native Network Implementation

We will transition the Ring Road from being explicit physical "blocks" (thick grey) to being a native part of the dynamic A* road network (rendered as pink/normal roads in the dashboard).

## User Feedback
- "keep it pink as it is" - The Ring Road will be styled as a standard road segment (pink).

## Proposed Changes

### `Core/Groups.py`
- [x] Remove the `PB Road NS` and `PB Road EW` entries from the `FOOTPRINTS` and `GROUP_COLORS` dictionaries.
- [x] Revert the `compute_entrance_points` and `get_all_groups` functions to remove the hacky `PB Road` overrides.

### `Core/Main.py`
- [x] Remove the injection of `PB Road NS_N`, `PB Road NS_S`, etc. into the `placed` dictionary after the Power Block is placed.
- [x] Revert the rack intersection and double-gap hotfixes from `_try_place_collision_aware`, since the Ring Road will no longer act as a fake building.
- **Why this works:** The layout engine naturally forces a **15m empty space** around the Power Block. This is more than enough room for an 8m road (with a 3m inner buffer), so the buildings will naturally pack themselves *around* this invisible road corridor.

### `Core/Roads.py`
- [x] In `build_road_network`, calculate a mathematical ring exactly **7m** off the edge of the Power Block (3m setback + half of the 8m road).
- [x] Append this Ring Road loop explicitly into the `segments` list that the pathfinder returns.
- [x] Skip A* routing to Power Block entrances (they sit inside the 6m inflate buffer; the Ring Road segment covers PB connectivity).
- **Result:** The A* algorithm will draw the road completely around the PB, and as the Gate and other buildings route their paths, they will naturally merge and connect to this existing corridor.

## Verification Plan
1. Generate a layout.
2. Verify that the Power Block has an unbroken pink road surrounding it.
3. Verify that the Cooling Tower and Admin Building pack tightly around the road corridor without triggering overlap rejections.
4. Verify that the Gate connects smoothly to the overall network.

# Phase 06: Grid-First Generative Layout

**Replaces:** Phase 05 (continuous coordinate placement + entrance-based A* routing)  
**Status:** Planning — Step 1 in implementation, Step 2 deferred

---

## Core Concept

Two-pass generative system. Step 1 sketches the site at **block + road level**. Step 2 (deferred) refines each block into individual buildings with entrance connections.

Roads come **before** buildings. Blocks are placed around roads, not the other way around.

---

## Block Catalog (from Plot Plan Requirement)

Each "block" is a footprint zone that contains one or more buildings. Current confirmed blocks:

| Block Name | Contents | Notes |
|---|---|---|
| Power Block | GT Building (1), ST Building (2), HRSG (3), Control Bldg (4), Main Stack (5), Transformers (6-9) | Central anchor — placed first |
| GIS | 345kV GIS (10), GIS Control Bldg (11) | Near NE boundary |
| Cooling Tower | Cooling Tower (12), CW Pump (13), CT Electrical (14) | Leeward zone |
| LPG/Metering | LPG Governor (15), Fuel Gas Filter (16), LPG Heater (17), LPG Surge Drum (18), LPG Metering Skid (63) | Near boundary (gas tie-in) |
| Flare | Flare Stack (19), Flare KO Drum (48), N2 for Flare (50) | Leeward corner |
| WT/WWT | WT/WWT Bldg (21), Chemical Storage (22), Clarifier WWT (23), Clarifier RW (24), WT/WWT Pump Room (62) | Downwind |
| RAW Water | RAW Water Tank (25), RAW Water Buffer Pond (49), RAW Water Supply Pump (54) | Near water tie-in |
| Demi Water | Demi Water Tank (26), Potable Water Tank (27) | Near RAW Water |
| Admin | Admin Building (28), Parking (41) | Near Gate |
| Gate House | Gate House (29) | Fixed on boundary |
| Warehouse | Machine Shop & Warehouse (30), AUX/LPG Boiler (31), Oil Storage (40) | Near boundary road |
| Fire Water | Fire Water Pump House (55) | Near boundary |
| EDG | EDG Building (47) | Near PB |

---

## Step 1: Block + Road + Rack Sketch

### 1.1 Grid Setup
- Cell size: **2m × 2m**
- Site: 500m × 270m → grid is **250 × 135 cells**
- All block positions snap to grid (no floating point coordinates)
- Each block has a configurable **buffers**

### 1.2 Placement + Rack + Fire Road Sequence

**Racks are more important than roads** — they're placed before perimeter/spurs/stubs so roads route around the rack corridors. Full sequence:

```
1. Place fixed anchors           (Gate House, GIS, RAW Water)
2. Place Power Block + PB Ring Road  (ring must NOT intersect any fixed anchor)
3. Place floated blocks          (Cooling Tower, WT/WWT, Warehouse, Flare, Admin, Demi)
4. → Place RACKS                 (single 6m Pipe Rack, see § 1.2-RACK below)
5. → Draw Perimeter Fire Road    (polygon, avoids all placed blocks + racks)
6. → Draw gate + ring spurs      (connect both fire roads to Gate)
7. → Draw block stubs            (each block → both fire roads)
```

---



### 1.3 Block Placement Order

| # | Block | Type | Rule | Buffer |
|---|---|---|---|---|
| 1 | **Gate House** | Fixed anchor | User-defined edge + ratio | 8m |
| 2 | **GIS** | Fixed anchor | User-defined edge + ratio | 8m |
| 3 | **RAW Water** | Fixed anchor | User-defined edge + ratio | 8m |
| 4 | **Power Block** | Soft anchor | Site center ± jitter | 8m |
| ↓ | *→ PB Ring Road drawn here* | — | — | — |
| 5 | **Cooling Tower** | Floated | Leeward zone, explicitly snaps to PB | 8m |
| 6 | **WT/WWT** | Floated | Near RAW Water, explicitly snaps to PB | 8m |
| 7 | **Warehouse** | Floated | Available space, explicitly snaps to PB | 8m |
| 8 | **Flare** | Floated | Leeward corner | 8m |
| 9 | **Admin** | Floated | Near Gate + PB, explicitly snaps to PB | 8m |
| 10 | **Demi Water** | Floated | Near RAW Water, explicitly snaps to RAW Water | 8m |
| ↓ | *→ Perimeter Fire Road drawn here* | — | — | — |


+ See buffer rules from Step A — Buffer layers per block

I want to design the floated-block placement so blocks snap onto each other's road-buffer lines like magnets, with these rules:
- **Plot Boundary Leeway:** A `BOUNDARY_TOLERANCE` of 10m is allowed during layout generation to provide leeway for tight border fits.
- **Ignore Fixed Anchors:** Floated blocks do NOT use Fixed Anchors (Gate House, GIS, RAW Water) as default magnets. This guarantees they form a cohesive central cluster instead of stranding near the borders. (Exception: Demi Water is hardcoded to target RAW Water).
- rack blocks ↔ rack blocks: snab by using the 14m road buffer (so their block edges sit 28m apart on that side)
- no-rack blocks ↔ no-rack blocks : share the 8m road buffer (16m apart)
- mixed rack/no-rack blocks: connect via b2b buffer (no shared road; sit block edges sit 28m apart)
- **Gate Death Zone Avoidance:** ALL floated blocks must strictly avoid overlapping the Gate Death Zone.

### 1.2-RACK Pipe Rack Algorithm

Single rack type, **width = 6 m**, connects the 5 "need rack" blocks: **PB, Cooling Tower, WT/WWT, RAW Water Tank, Demi Water Tank**. (Cable Tunnel GIS↔PB is separate logic, not part of this step.)

#### Step A — Buffer layers per block

**Non-rack blocks** (Gate House, Warehouse, Flare, Admin, GIS) — 2 offsets:
| Key            | Offset | Meaning                                    |
| -------------- | ------ | ------------------------------------------ |
| `road`         |   8 m  | Road centerline must be ≥ 8 m from edge    |
| `b2b`          |  16 m  | Block-to-block edge-to-edge gap            |

**"Need rack" blocks** (PB, Cooling Tower, WT/WWT, RAW Water Tank, Demi Water Tank) — 6 offsets per block. Two regimes per side: "no rack" (default) and "with rack" (the side actually carries a rack):

| Key             | Offset | Regime    | Meaning                                          |
| --------------- | ------ | --------- | ------------------------------------------------ |
| `road_no_rack`  |   8 m  | no rack   | Road CL on a side without a rack (baseline)      |
| `b2b_no_rack`   |  16 m  | no rack   | Block-to-block on a side without rack (baseline) |
| `case1_rack`    |   6 m  | with rack | Rack CL — Case 1 (block → rack → road)           |
| `road_w_rack`   |  14 m  | with rack | Road CL on a side that has a rack                |
| `case2_rack`    |  22 m  | with rack | Rack CL — Case 2 (block → road → rack)           |
| `b2b_w_rack`    |  28 m  | with rack | Block-to-block on a side that has a rack         |

Block-side decision (which regime applies) is made by Step B/C of rack routing. During Step 1.3 floated-block placement the **baseline** offsets are used for all blocks; the larger "with-rack" offsets are precomputed in Step A and enforced later if/when a rack lands on that side.

Cell size: 2 m throughout. The active rack-buffer rectangle per rack block is chosen as follows:
- **PB and Cooling Tower:** Chosen at random between Case 1 and Case 2.
- **Demi Water, WT/WWT, RAW Water:** Locked to Case 1 Rack only.

#### Step B — Build spine segments

**B-1 (PB↔CT spine):** PB and Cooling Tower each have 2 rack-buffer rectangles (Case 1 and Case 2). For each block, randomly pick one case — this selects the active rack buffer rectangle. Take the closest side whose direction (or reverse direction) is looking to RAW Water Tank → those 2 rack-buffer lines become the **PB↔CT spine centerlines** (2 parallel lines).

**B-2 (RAW points):** RAW Water Tank's active rack-buffer rectangle has 4 corner points. Any point landing outside the plot boundaries is completely pruned. Measure distance from each remaining corner to the **center point** of PB's selected rack-buffer line (from B-1). Keep the **2 closest corners** as the candidate RAW points.

**B-3 (Demi points):** Same as B-2 for Demi Water Tank → Prune out-of-bounds corners, keep 2 candidate Demi points.

**B-4 (Pick WWT join point):** Take all 4 candidate points (2 RAW from B-2 + 2 Demi from B-3). For each, try a perpendicular projection onto the nearest side of WWT's active rack-buffer rectangle. Prune any projection that lands outside the WWT side segment.

- *If ≥1 projection succeeds:* form candidate lines from each surviving source point to its projected point on WWT. Take the **shortest** line.
  - The WWT endpoint of that line = the kept WWT point.
  - The other endpoint is on RAW or Demi:
    - If on **RAW** → keep it as RAW point; find closest of the 2 Demi candidates to that RAW point → that's the Demi point.
    - If on **Demi** → keep it as Demi point; find closest of the 2 RAW candidates to that Demi point → that's the RAW point.
- *If no projection succeeds:* take WWT rack buffer 4 edge points (corners) and find the one closest to RAW Water Tank center. This is the kept WWT point. Among the 4 candidate points, take the one closest to this WWT point. Apply the same RAW/Demi selection rule above.

Result: **3 points** — one each on RAW, Demi, and WWT rack buffer lines, forming the tightest triangle.

**B-5 (Water cluster spine):** Connect the 3 points using **orthogonal paths only** (no diagonals). Paths can travel along any block's active rack-buffer line or through empty grid cells. Cannot intersect any block footprint.

#### Step C-1 — Connect spines into one network

The **PB↔CT spine** (from Step B-1) actually consists of two separate, parallel line segments (one for the PB block, one for the CT block). We connect these lines and the **water cluster spine** into a single unified network using a two-stage orthogonal routing sequence:

1. **First Connection:** Route the shortest orthogonal path from the **water cluster spine** to the closest of the two PB/CT lines.
2. **Second Connection:** Take the newly expanded connected network (water cluster + path + the hit line) and route the shortest orthogonal path from this combined network to the **remaining disconnected line** (CT or PB).

For both routing passes, the connection path must:
- Extend an existing spine line, OR
- Route along another "need rack" block's active rack-buffer line (Case 1 or Case 2),
- Never cross any block footprint.

#### Step C-2 — Flare Pipe Rack Connection

After unifying the main rack network, we must connect the **Flare** block to this network.

1. **Check for existing intersection:** If any segment of the unified network already touches or intersects the Flare's active rack buffer rectangle, the connection is satisfied. No additional spines are added.
2. **Find shortest real-path connection:** If not connected, take the 4 edge points (corners) of the Flare's active rack buffer.
   - For each corner, find an orthogonal path to the unified network.
   - This routing **must avoid all block footprints** (obstacles in the line of sight).
   - Compare the paths and select the corner that yields the shortest "real" routed path length (accounting for obstacles, not just direct straight-line distance).
3. Add this shortest orthogonal path to the unified network.

#### Output

A single connected rack polyline network (centerlines, 6 m wide). The network becomes an obstacle for later perimeter/spur/stub placement.

**A-1. PB Ring Road & Gate House (Special Cases)**
- Centerline offset: **8m** from each PB block face
  `= 4m setback (block edge → road edge) + 4m (half of 8m road width)`
- Visual rule: `block ←4m gap— road edge ——4m—→ centerline`
- Drawn as **line segments** (graph edges) — not rasterized to cells
- Must not intersect any placed block
- **Routing to Gate (Boom Barrier Integration):**
  1. Identifies the "exit line" between the Boom Barrier midpoint and the physical Gate.
  2. Projects the two road buffer corners of the selected Gate House side onto this exit line.
  3. Routes: PB Ring Road → *unprojectable* corner → Boom Barrier midpoint (perfect 90-degree crossing) → *projectable* corner → Gate.
  4. **Gate Death Zone:**
     - Extend the road buffer line from step 2 in both directions to the plot boundaries, dividing the site into two surfaces.
     - Select the surface that contains the physical Gate.
     - The Boom Barrier line splits this surface into two halves.
     - Select the half that contains the *projectable* corner from step 2.
     - This resulting rectangular area is the "Gate Death Zone" (to be used later when placing the Perimeter Fire Road).

**A-2. Block Access Logic (8m Roads)**
This defines how the remaining blocks connect to the road network.
**Important:** We work with the block's **rack buffer lines**, not the physical block footprint itself! Each block is a rectangle with 4 corners, meaning each corner is formed by 2 intersecting buffer lines.

**Corner Selection Rules:**
- **"Corner near boundary":** Select the buffer corner closest to the plot boundary, and select its 2 lines.
- **"Corner near PB":** Select the buffer corner closest to the Power Block, and select its 2 lines.
- **Tie-breaker:** If multiple corners are exactly the same distance to the boundary or PB, pick one randomly.

**Priority Rule (For blocks needing 2 corners):**
`Perimeter corner > PB corner`
For blocks that require 2 corners (like GIS, Cooling Tower, Warehouse):
1. First, find the closest corner to the perimeter (select randomly if there's a tie).
2. Then, choose the **opposite diagonal corner** for the second point (no need to independently search for the closest point to the PB).

**Exception (RAW Water Tank):**
- Must pick the corner near the boundary that is **furthest from the Demi Water Tank**. If there are multiple corners equally close to the boundary, select the one that maximizes the distance to the Demi Water Tank.
**B. Perimeter Fire Road**

There will be 2 parts for B:

**B-1 Segment Generation Algorithm**
- **Pass 1 — Direct intersections:** For every pair of fire-road blocks, check if their exact road buffer lines intersect. If a block has multiple intersections, take ALL possible line intersections (this helps stitch closely packed blocks together).
- **Pass 2 — Tolerance pass:** (only for blocks not yet connected): Expand the road buffer by +6m and re-check.
  - 2a) Line intersection → use it.
  - 2b) Surface (rectangle overlap) intersection → take the longest centerline through the overlap region *(this will naturally lay in the empty space between their original road buffers)*.
- **Pass 3 — Orphans:** For any block still unconnected, take its EXACT road buffer line (edge) farthest from PB and use that as its fire road segment.
### 1.4 Connect Blocks to Fire Road Network

For each block (except Gate House which sits on the perimeter road):
1. Find **nearest point** on PB Ring Road → draw **obstacle-avoiding** connection line (routes around other blocks)
2. Find **nearest point** on Perimeter Fire Road → draw **obstacle-avoiding** connection line

Each block gets exactly **2 stub connections** — one to each fire road.  
All stubs become candidate road segments added to the road graph.


### 1.6 Road Classification

After pruning, classify each remaining segment:

| Condition | Road Type | Width |
|---|---|---|
| Part of PB Ring Road | **Primary (Fire)** | 8m |
| Part of Perimeter Fire Road | **Primary (Fire)** | 8m |
| Stub connection (any block, any usage count) | **Secondary** | 6m |

**Compaction rule:** Blocks adjacent only to Secondary roads may shift **3m closer** to that road centerline  
(secondary buffer = 3m each side vs primary buffer = 4m each side).

### 1.7 Step 1 Output

```python
{
  "grid":             Grid(cell_size=2),
  "blocks":           [{"name", "x", "y", "width", "height", "buffer_m"}],
  "road_graph":       Graph,              # all kept segments as edges
  "fire_segments":    [LineSegment],      # Primary — fire roads
  "secondary_segs":   [LineSegment],      # Secondary — block stubs
  "gate_point":       (x, y),
  "PERIMETER_SETBACK": 5,                # configurable constant
}
```

All roads are **sketch roads** — centerlines only (lines), no physical width rendered yet.

---

## Step 2: Building Finalization (Deferred)

> To be implemented after Step 1 is validated.

High-level intent (for Step 1 design awareness):

1. **Place buildings inside each block** — buildings subdivide the block footprint
2. **Add building entrances** — each building gets a door facing the nearest sketch road
3. **Adjust road geometry** — road centerlines shift to align with actual building faces
4. **Finalize** — sketch roads become confirmed roads with physical width; buildings lock in position
5. **Access roads** — short stubs from building entrance to nearest road centerline

Step 2 knows Step 1's road network, so buildings work around committed roads.

---

## Key Differences from Phase 05

| | Phase 05 | Phase 06 |
|---|---|---|
| Coordinate system | Continuous float (metres) | Snapped to 2m grid |
| Road creation | A* from gate to each building entrance | Road graph first, blocks placed around it |
| Building entrances | Required for routing | Not used in Step 1; deferred to Step 2 |
| Ring Road | Hand-injected geometry segment | Native graph edge (line), merges with perimeter where overlapping |
| Road classification | Single type | Primary (fire) / Secondary (stubs) / Access (Step 2) |
| Block buffers | Fixed 15m all sides | 8m default, compresses 3m near secondary roads |
| Perimeter road shape | Rectangle only | Polygon — 4–6+ sides |
| Perimeter setback | Hard-coded | `PERIMETER_SETBACK` configurable constant |

---

## Open Questions

- [ ] Which blocks should have **fixed** vs **compressible** buffers?
- [ ] Stub routing: simple detour around block bounding box, or full A* on 2m grid?
- [ ] When ring and perimeter merge: snap to one centerline or average?

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

## Step 1: Block + Road Sketch

### 1.1 Grid Setup
- Cell size: **2m × 2m**
- Site: 500m × 270m → grid is **250 × 135 cells**
- All block positions snap to grid (no floating point coordinates)
- Each block has a configurable **buffer** (default: 8m = half of primary road width)

### 1.2 Placement + Fire Road Sequence

Fire roads are derived from block positions — they come **after** the blocks they depend on. Full sequence:

```
1. Place fixed anchors   (Gate House, GIS, RAW Water)
2. Place Power Block     (center anchor ± jitter)
3. → Draw PB Ring Road   (geometry derived from PB position)
4. Place floated blocks  (Cooling Tower, WT/WWT, Warehouse, Flare, Admin, Demi, EDG, Fire Water)
5. → Draw Perimeter Fire Road  (polygon, avoids all placed blocks)
6. → Connect both fire roads to Gate
```

**A. PB Ring Road**
- Centerline offset: **8m** from each PB block face
  `= 4m setback (block edge → road edge) + 4m (half of 8m road width)`
- Visual rule: `block ←4m gap— road edge ——4m—→ centerline`
- Drawn as **line segments** (graph edges) — not rasterized to cells
- Must not intersect any placed block
- Connected directly to the Gate (path along ring to Gate entry point)

**B. Perimeter Fire Road**
- **Polygon** loop — follows site boundary shape
  *(supports 4–6+ sides for non-rectangular real site boundary in future)*
- Outer edge setback from plot boundary: **`PERIMETER_SETBACK = 5m`** *(configurable constant)*
- Road centerline at: `PERIMETER_SETBACK + 4m = 9m` from boundary
- Drawn as **line segments** (graph edges)
- Routes **around** all placed blocks (obstacle-aware polygon routing)
- Connected to the Gate (entry point on boundary)
- Where PB Ring Road and Perimeter Fire Road **overlap or are adjacent** → merged into one segment (no duplicate edges in graph)

### 1.3 Block Placement Order

| # | Block | Type | Rule | Buffer |
|---|---|---|---|---|
| 1 | **Gate House** | Fixed anchor | User-defined edge + ratio | 8m |
| 2 | **GIS** | Fixed anchor | User-defined edge + ratio | 8m |
| 3 | **RAW Water** | Fixed anchor | User-defined edge + ratio | 8m |
| 4 | **Power Block** | Soft anchor | Site center ± jitter | 8m |
| ↓ | *→ PB Ring Road drawn here* | — | — | — |
| 5 | **Cooling Tower** | Floated | Leeward zone, closest to PB | 8m |
| 6 | **WT/WWT** | Floated | Near RAW Water, closest to PB | 8m |
| 7 | **Warehouse** | Floated | Available space | 8m |
| 8 | **Flare** | Floated | Leeward corner | 8m |
| 9 | **Admin** | Floated | Near Gate + PB | 8m |
| 10 | **Demi Water** | Floated | Near RAW Water | 8m |
| 11 | **EDG** | Floated | Near PB | 8m |
| 12 | **Fire Water** | Floated | Near boundary | 8m |
| ↓ | *→ Perimeter Fire Road drawn here* | — | — | — |

**Buffer rule:** No block may be placed within **8m** of another block's edge. Buffer is adjustable per block pair.

### 1.4 Connect Blocks to Fire Road Network

For each block (except Gate House which sits on the perimeter road):
1. Find **nearest point** on PB Ring Road → draw **obstacle-avoiding** connection line (routes around other blocks)
2. Find **nearest point** on Perimeter Fire Road → draw **obstacle-avoiding** connection line

Each block gets exactly **2 stub connections** — one to each fire road.  
All stubs become candidate road segments added to the road graph.

### 1.5 Path Verification (2-Path Check)

For each block, find **2 paths to Gate** using the two stub connections:

- **Path 1:** Block → *PB Ring Road stub* → traverse fire road graph → Gate *(shortest)*
- **Path 2:** Block → *Perimeter Fire Road stub* → traverse fire road graph → Gate *(shortest)*

Paths may share some segments (e.g. both merge onto the same perimeter arc near Gate), but they **start from different stubs** so they are always structurally different.

After finding both paths for **all blocks**:
- Segments **used by ≥1 path** of any block → **keep**
- Segments **used by no path** → **prune**

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

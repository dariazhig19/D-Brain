## Road Access per Block — Complete Table

| #   | Block         | 8m Roads | 6m Roads | Total Roads | Access Point Positions                                  | Notes                                      |
| --- | ------------- | -------- | -------- | ----------- | ------------------------------------------------------- | ------------------------------------------ |
| 1   | Gate House    | 1        | 0        | 1           | 1 on perimeter side (the gate itself)                   | Gate IS the access point                   |
| 2   | GIS           | 2        | 0        | 2           | Corner near boundary (8m) + corner near PB (8m)         |                                            |
| 3   | RAW Water     | 1        | 1        | 2           | Corner near boundary (8m) + corner near WT/WWT (6m)     | Chemical/maintenance delivery              |
| 4   | Power Block   | 1 (ring) |          |             | 4 corners of ring road                                  |                                            |
| 5   | Cooling Tower | 2        | 0        | 2           | Corner near perimeter (8m) + corner near PB (8m)        |                                            |
| 6   | WT/WWT        | 1        | 1        | 2           | Corner near perimeter (8m) + corner near RAW Water (6m) | Truck-heavy chemical delivery on 8m side   |
| 7   | Warehouse     | 2        | 0        | 2           | Corner near perimeter (8m) + corner near PB (8m)        | Wide delivery access on 8m side            |
| 8   | Flare         | 0        | 1        | 1           | Corner on plant-facing side only                        | NEVER on boundary/leeward side (radiation) |
| 9   | Admin         | 1        | 1        | 2           | Corner near Gate (8m) + corner opposite (6m)            |                                            |
| 10  | Demi Water    | 0        | 1        | 1           | Corner near pump skid (PB-facing)                       | Low-traffic, single access sufficient      |
|     |               |          |          |             |                                                         |                                            |

## Road Access — Grouped by Road Type

### Special Cases (kept separate)

| # | Block | Road | Access Points |
|---|---|---|---|
| 1 | Gate House | 8m (perimeter) | 1 — the gate itself |
| 4 | Power Block | 8m (ring road) | 4 corners of ring |

---

### Group A — 8m Road Side

Blocks that need an 8m road connection on at least one side:

| #   | Block         | 8m Count | Access Point Position                  |
| --- | ------------- | -------- | -------------------------------------- |
| 2   | GIS           | 2        | Corner near boundary + corner near PB  |
| 3   | RAW Water     | 1        | Corner near boundary                   |
| 5   | Cooling Tower | 2        | Corner near perimeter + corner near PB |
| 6   | WT/WWT        | 1        | Corner near perimeter                  |
| 7   | Warehouse     | 2        | Corner near perimeter + corner near PB |
| 9   | Admin         | 1        | Corner near Gate                       |

**Group C total: 9 × 8m connections across 6 blocks**

---

### Group B — 6m Road Side

Blocks that need a 6m road connection on at least one side:

| # | Block | 6m Count | Access Point Position |
|---|---|---|---|
| 3 | RAW Water | 1 | Corner near WT/WWT |
| 6 | WT/WWT | 1 | Corner near RAW Water |
| 8 | Flare | 1 | Corner on plant-facing side |
| 9 | Admin | 1 | Corner opposite to Gate |
| 10 | Demi Water | 1 | Corner near pump skid (PB-facing) |

**Group D total: 5 × 6m connections across 5 blocks**

---

### Blocks Appearing in Both Groups (have both road types)

| # | Block | 8m | 6m |
|---|---|---|---|
| 3 | RAW Water | ✓ | ✓ |
| 6 | WT/WWT | ✓ | ✓ |
| 9 | Admin | ✓ | ✓ |

---

### Grand Totals

| | Count |
|---|---|
| 8m connections (Group C + Gate + PB) | 9 + 1 + 1 = **11** |
| 6m connections (Group D) | **5** |
| **Total road connections** | **16** |

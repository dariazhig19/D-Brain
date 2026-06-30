# Polygon Plot Migration — Step-by-Step Plan

> **What we are doing.** Today the plot is always a **rectangle**. We are changing
> it so the plot can be **any shape with up to 6 straight sides, including
> diagonal (slanted) sides**.
>
> We do this **one phase at a time**. After each phase we check two things:
> 1. A normal **rectangle** still works exactly like before (nothing breaks).
> 2. A **diagonal plot** also works (the new feature).
>
> - The full updated explanation is in [`PROJECT_Polygon.md`](PROJECT_Polygon.md).
> - The original rectangle explanation stays in [`PROJECT.md`](PROJECT.md).

---

## The big idea (why this is safe)

- A **rectangle is just a polygon with 4 corners**. So the new code treats every
  plot as a polygon, and a rectangle is simply one special case.
- We built a new helper, [`Core/Plot.py`](Core/Plot.py), that holds the plot shape
  and answers questions like *"is this block inside the plot?"*.
- **Important:** for a rectangle, the new helper gives the **exact same answer**
  as the old code. We proved this with an automatic test that checks 23,820
  cases — all match. So switching to the polygon **cannot change** how rectangles
  behave.

---

## How the plot is drawn (the CAD file)

- You **draw the plot in CAD** (AutoCAD) and the program reads it from the file.
- There are **no more sliders** for placing the gate, gate house, GIS, or RAW
  tank. They all come from the drawing.
- The **only setting left in the screen** is the **wind direction**.

Each item must be on its **own layer**, with these exact layer names:

| Layer in the drawing       | What you draw        | What it becomes in the program          |
|----------------------------|----------------------|------------------------------------------|
| `Plot`                     | one closed line (up to 6 corners) | the plot **outline**        |
| `Gate`                     | a **circle**         | the gate point (circle **center**)       |
| `Gate House`               | a rectangle          | the gate house building                  |
| `RAW Tank`                 | a **circle**         | the RAW water tank                       |
| `GIS`                      | a rectangle          | the GIS building                         |
| `Gate House Boom Barrier`  | a **line**           | the boom barrier                         |

- **DXF vs DWG.** The program reads **DXF** directly. **DWG** is AutoCAD's own
  format and needs an extra free converter (ODA File Converter). The easy way:
  in AutoCAD use **Save As → DXF**.

---

## Phase list (where we are)

| Phase | What it does | Status |
|-------|--------------|--------|
| **0** | Build the plot helper, read the CAD file, show it on screen | ✅ Done |
| 1 | Make the engine check "inside the plot" against the polygon | ✅ Done |
| 2 | Take the gate, gate house, GIS, RAW, boom **from the drawing** | ✅ Done |
| 3 | Place the Power Block and the leeward/flare zones using the polygon | ✅ Done |
| 4 | Check the floating blocks respect diagonal sides | ✅ Done |
| 5 | Make the gate road + ring road work with the CAD boom | ✅ Done |
| 6 | Pipe racks generate on the polygon (keep off the cut corners) | ✅ Done (for now) |
| 7 | Make the perimeter fire road follow the diagonal sides | ⬜ (skipped for now) |
| 8 | Make the small access roads use the nearest polygon side | ⬜ (skipped for now) |
| 9 | Re-center: move the polygon, not just a rectangle | ✅ Done |
| 10 | Draw the final result and export it as a polygon | ⬜ (skipped for now) |

> **Note on Phase 9.** Recenter now runs in the polygon (blocks-only) path. It
> computes the content bounding-box center (blocks + ring road + gate/ring spur +
> boom + rack network), then **slides the whole plot polygon** by
> `delta = content_center − plot_bbox_center` (`Plot.translate`). The **gate moves
> only perpendicular to its boundary edge** (the true perpendicular component of
> `delta`, so it works on diagonal sides), the gate spur's final L is rebuilt to
> reach it, and the gate death zone is recomputed. Outputs `plot_polygon`,
> `plot_polygon_before`, `gate_point_before`, `recenter_delta`; the dashboard draws
> the before-recenter polygon faded under the "§3.8 — Plot + gate before recenter"
> toggle.

> **Note on Phase 5.** The gate spur now uses the **original (pre-migration)
> gate-spur logic**, not a simplified one. We kept all its rules — `exit_helper` /
> `other_corner` chosen by projection onto the gate→boom line, the perfect **90°
> boom crossing** (`[exit_helper, bb_mid, other_corner, …, gate]`), the ring-spur
> U-turn check, and the gate death zone. The only changes for the polygon:
> - the boom edge (N/S/E/W) and midpoint are read from the **CAD boom line**
>   (`_boom_edge_and_mid`), so the spur crosses the boom where it is drawn;
> - the tie-break uses the **plot centre** instead of `sw/2, sl/2` (identical for a
>   rectangle);
> - **ring-spur connection fix:** when `exit_helper` is **outside** the ring road's
>   x/y span, the ring spur routes from the closest ring **corner** with a
>   perpendicular final approach, so it always reaches the ring road (before, it
>   could land just off the ring).

> **Note on Phase 6.** Pipe racks now **generate on the polygon**. Done so far:
> - rack grids are **masked to the polygon** (`_mask_grid_to_plot`) so racks never
>   cross a diagonal/cut corner;
> - in polygon mode the overlap short-cuts are skipped → **MAIN RACK** is just the
>   PB-centre→PB-buffer stub and the **PB↔CT connection always uses A\*** (routes
>   around blocks like the Warehouse);
> - the **Flare** connects to the nearest segment of the whole rack network;
> - **water-cluster free-end cleanup** anchored to the water-triangle points
>   (reverts any trim that drops a water-buffer touch) — *still being refined*.

---

## Phase 0 — Foundation (done today)

**Goal:** read the CAD file and show the plot on screen. The layout engine is
**not touched yet**, so nothing can break.

**What we built:**

- **`ezdxf`** library installed (this is what reads CAD files).
- [`Core/Plot.py`](Core/Plot.py) — the plot helper. It can:
  - tell if a point or a block is **inside the plot**,
  - find the plot **center**,
  - **shrink the plot inward** (used later for the perimeter road),
  - **move** the whole plot.
- [`Core/cad_import.py`](Core/cad_import.py) — reads the CAD file by layer and
  gives back the plot, gate, boom, and the three buildings. It also:
  - **fixes the units automatically** (the drawing was in **millimetres**; it
    converts to **metres**),
  - **moves the drawing to start at (0,0)**,
  - reads tanks drawn as **circles**.
- [`tests/test_plot.py`](tests/test_plot.py) — automatic checks. **6 of 6 pass.**
- The **dashboard** now:
  - reads the DXF **from disk** (browser upload is blocked on your PC),
  - shows only **wind direction** plus a hidden "rectangle fallback" box,
  - draws a **preview** of the plot, gate, boom, and buildings.

**Checked against your real drawing** (`Data/sample_plot.dxf`):

- It is a **5-sided plot** (rectangle with one diagonal corner), 512 × 280 m.
- Units were read as **millimetres** and converted to metres correctly.
- The **gate sits exactly on the boundary**.
- Gate House, GIS, and RAW Tank are the **right sizes** and **inside the plot**.

> [!IMPORTANT]
> **One surprise from your drawing.** Your **gate is on a slanted (diagonal)
> side**, but the boom barrier is drawn straight up-and-down. This means
> **Phase 5** really does need to handle a boom on a diagonal side — it is not
> optional. This is noted so we don't forget.

**What Phase 0 does NOT do yet:**

- The layout engine still builds layouts on a **rectangle**.
- Connecting the real polygon into the engine **starts in Phase 1**.

---

## What each next phase will do (short version)

- **Phase 1 — Inside check.** Replace the old "inside the rectangle" test with the
  new "inside the polygon" test everywhere in the engine.
- **Phase 2 — From the drawing.** The gate, gate house, GIS, RAW tank and boom are
  taken straight from the CAD file instead of from sliders.
- **Phase 3 — Power Block & zones.** Place the Power Block relative to the plot
  **center**, and put the Flare in the **leeward corner of the polygon**.
- **Phase 4 — Floating blocks.** Make sure blocks like Cooling Tower and WT/WWT
  don't poke past a diagonal side.
- **Phase 5 — Gate road & ring road.** Reuse the original gate-spur logic; cross
  the boom correctly using the CAD boom line.
- **Phase 6 — Pipe racks.** Generate racks on the polygon; keep them off cut corners.
- **Phase 7 — Perimeter fire road.** Follow the diagonal sides.
- **Phase 8 — Access roads.** Use the nearest polygon side.
- **Phase 9 — Re-center.** Move the whole **polygon**, not a rectangle.
- **Phase 10 — Draw & export.** Show and export the plot as a polygon.

---

## Files in this migration

| File | What it is |
|------|------------|
| [`Core/Plot.py`](Core/Plot.py) | the plot-shape helper (Phase 0) |
| [`Core/cad_import.py`](Core/cad_import.py) | reads the CAD file (Phase 0) |
| [`tests/test_plot.py`](tests/test_plot.py) | automatic checks (Phase 0) |
| [`PROJECT_Polygon.md`](PROJECT_Polygon.md) | full updated explanation |
| `PLAN_Polygon_Migration.md` | this plan |
| `Data/sample_plot.dxf` | your real drawing (used for testing) |
| `Data/sample_plot.dwg` | the original AutoCAD file (needs a converter) |

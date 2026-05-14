"""Occupancy grid for PowerPlan AI layouts.

Discretises the site into uniform square cells (default 2.5 m) so that
infrastructure routing (roads, racks) can be posed as discrete path-planning
problems on top of building placement. Coordinate convention: ``grid[i, j]``
indexes the cell whose lower-left corner sits at world ``(i*cell_size,
j*cell_size)``. ``i`` runs along the site width (x), ``j`` along the length (y).
"""

import math
import numpy as np


CELL_SIZE = 2.5   # metres — matches RACK_TO_BLOCK clearance


class Grid:
    """A 2D occupancy grid over a rectangular site.

    Cells are ``True`` when blocked (building, setback) and ``False`` when free.
    """

    def __init__(self, site_w, site_l, cell_size=CELL_SIZE):
        self.site_w = float(site_w)
        self.site_l = float(site_l)
        self.cell_size = float(cell_size)
        self.ncols = int(math.ceil(self.site_w / self.cell_size))
        self.nrows = int(math.ceil(self.site_l / self.cell_size))
        self.blocked = np.zeros((self.ncols, self.nrows), dtype=bool)

    # ── Coordinate conversion ─────────────────────────────────────────────

    def world_to_cell(self, x, y):
        """World metres → cell index. Clamps to grid bounds."""
        i = int(x / self.cell_size)
        j = int(y / self.cell_size)
        i = max(0, min(self.ncols - 1, i))
        j = max(0, min(self.nrows - 1, j))
        return i, j

    def cell_to_world(self, i, j):
        """Cell index → world metres at the cell *centre*."""
        return ((i + 0.5) * self.cell_size, (j + 0.5) * self.cell_size)

    def in_bounds(self, i, j):
        return 0 <= i < self.ncols and 0 <= j < self.nrows

    def is_free(self, i, j):
        return self.in_bounds(i, j) and not self.blocked[i, j]

    # ── Marking ───────────────────────────────────────────────────────────

    def mark_building(self, building, inflate_m=3.0):
        """Block all cells overlapping a building, inflated by ``inflate_m``.

        ``building`` is a dict with ``x``, ``y``, ``width``, ``height`` in metres.
        Conservative: any cell whose footprint touches the inflated rect is
        marked blocked.
        """
        x0 = building["x"] - inflate_m
        y0 = building["y"] - inflate_m
        x1 = building["x"] + building["width"] + inflate_m
        y1 = building["y"] + building["height"] + inflate_m
        i0 = max(0, int(math.floor(x0 / self.cell_size)))
        j0 = max(0, int(math.floor(y0 / self.cell_size)))
        i1 = min(self.ncols, int(math.ceil(x1 / self.cell_size)))
        j1 = min(self.nrows, int(math.ceil(y1 / self.cell_size)))
        self.blocked[i0:i1, j0:j1] = True

    def mark_buildings(self, buildings, inflate_m=3.0):
        for b in buildings:
            self.mark_building(b, inflate_m=inflate_m)

    def mark_setback(self, margin_m):
        """Block the outer ring of cells whose centres lie within ``margin_m``
        of the site boundary. Used to keep the road inside the setback zone.
        """
        xs = (np.arange(self.ncols) + 0.5) * self.cell_size
        ys = (np.arange(self.nrows) + 0.5) * self.cell_size
        x_mask = (xs < margin_m) | (xs > self.site_w - margin_m)
        y_mask = (ys < margin_m) | (ys > self.site_l - margin_m)
        self.blocked |= x_mask[:, None] | y_mask[None, :]

    # ── Debug ─────────────────────────────────────────────────────────────

    def free_cells(self):
        """Return list of (i, j) for all unblocked cells. Debug aid only."""
        return list(zip(*np.where(~self.blocked)))

    def __repr__(self):
        free = int((~self.blocked).sum())
        total = self.ncols * self.nrows
        return (f"Grid({self.ncols}×{self.nrows} @ {self.cell_size}m, "
                f"{free}/{total} free)")

"""A* path planning over an occupancy :class:`Grid`.

Designed for routing roads and racks: 8-connected, with a configurable
turn-penalty (smooths paths as a proxy for turn radius) and a width-aware
passability check (the corridor around each cell must also be clear).
"""

import heapq
import math
from itertools import count

import numpy as np


# 8-connected neighbours: (di, dj, step_cost)
_NEIGHBORS = [
    (1, 0,  1.0),  (-1, 0, 1.0),  (0, 1,  1.0),  (0, -1, 1.0),
    (1, 1,  math.sqrt(2)),  (1, -1, math.sqrt(2)),
    (-1, 1, math.sqrt(2)),  (-1, -1, math.sqrt(2)),
]


def _octile(a, b):
    """Octile distance — admissible heuristic for an 8-connected grid."""
    di = abs(a[0] - b[0])
    dj = abs(a[1] - b[1])
    return (max(di, dj) - min(di, dj)) + math.sqrt(2) * min(di, dj)


def _passable(grid, i, j, width_cells):
    """A cell is passable only if a (2*width_cells+1) square centred on it
    is entirely inside the grid and unblocked. Enforces road width.

    Slow path used only when no precomputed passability array is supplied.
    """
    for di in range(-width_cells, width_cells + 1):
        for dj in range(-width_cells, width_cells + 1):
            if not grid.is_free(i + di, j + dj):
                return False
    return True


def build_passable(grid, width_cells):
    """Vectorised morphological erosion of the grid's free space.

    Returns a ``numpy.bool_`` array shaped like ``grid.blocked`` where ``True``
    means a corridor of half-width ``width_cells`` fits centred on that cell.
    Compute once per layout, reuse across many :func:`astar` calls.
    """
    free = ~grid.blocked
    if width_cells <= 0:
        return free.copy()
    nc, nr = free.shape
    passable = free.copy()
    for di in range(-width_cells, width_cells + 1):
        for dj in range(-width_cells, width_cells + 1):
            if di == 0 and dj == 0:
                continue
            shifted = np.zeros_like(free)
            li = nc - abs(di)
            lj = nr - abs(dj)
            # shifted[a, b] = free[a + di, b + dj]; out-of-bounds stays False.
            shifted[max(0, -di):max(0, -di) + li,
                    max(0, -dj):max(0, -dj) + lj] = \
                free[max(0, di):max(0, di) + li,
                     max(0, dj):max(0, dj) + lj]
            passable &= shifted
    return passable


def snap_to_passable(passable, ij, max_radius=20):
    """Find the nearest passable cell to ``ij`` within ``max_radius`` cells
    (Chebyshev distance). Returns ``ij`` unchanged if already passable, or
    ``None`` if nothing passable lies within the radius.
    """
    nc, nr = passable.shape
    i0, j0 = ij
    if 0 <= i0 < nc and 0 <= j0 < nr and passable[i0, j0]:
        return ij
    for r in range(1, max_radius + 1):
        for di in range(-r, r + 1):
            for dj in range(-r, r + 1):
                if max(abs(di), abs(dj)) != r:
                    continue
                ci, cj = i0 + di, j0 + dj
                if 0 <= ci < nc and 0 <= cj < nr and passable[ci, cj]:
                    return (ci, cj)
    return None


def astar(grid, start_ij, goal_ij, *,
          turn_penalty=0.5,
          width_cells=1,
          allow_diagonal=True,
          passable=None):
    """A* search on an occupancy Grid with turn penalty and width check.

    Args:
        grid:           :class:`Grid` instance.
        start_ij:       (i, j) start cell.
        goal_ij:        (i, j) goal cell.
        turn_penalty:   Extra cost added when heading changes between steps.
                        Smooths the path (proxy for turn radius). 0 disables.
        width_cells:    Required clear half-width around every cell on the
                        path. ``width_cells=1`` enforces a 3-cell corridor.
        allow_diagonal: If False, restrict to 4-connected (cardinal) moves.
        passable:       Optional precomputed bool array from
                        :func:`build_passable`. When supplied, replaces the
                        per-state width check with an O(1) array lookup —
                        the hot-path optimisation for many A* calls on the
                        same grid.

    Returns:
        List of (i, j) cells from start to goal (inclusive), or ``None``
        if no path exists.
    """
    if passable is not None:
        nc, nr = passable.shape
        def _is_pass(ij):
            i, j = ij
            return 0 <= i < nc and 0 <= j < nr and bool(passable[i, j])
    else:
        def _is_pass(ij):
            return _passable(grid, ij[0], ij[1], width_cells)

    if not _is_pass(start_ij):
        return None
    if not _is_pass(goal_ij):
        return None

    moves = _NEIGHBORS if allow_diagonal else [m for m in _NEIGHBORS if m[2] == 1.0]

    # State = (cell, incoming_direction). Without direction in the state,
    # the turn penalty would not be admissible — two paths arriving at the
    # same cell from different headings have different remaining costs.
    counter = count()
    start_state = (start_ij, None)
    open_heap = [(_octile(start_ij, goal_ij), next(counter), 0.0, start_state)]
    best = {start_state: 0.0}
    came_from = {}   # state -> parent_state

    while open_heap:
        _, _, g, state = heapq.heappop(open_heap)
        cell, pdir = state

        if cell == goal_ij:
            path = [cell]
            while state in came_from:
                state = came_from[state]
                path.append(state[0])
            path.reverse()
            return path

        if best.get(state, math.inf) < g:
            continue

        for di, dj, step in moves:
            n = (cell[0] + di, cell[1] + dj)
            if not _is_pass(n):
                continue
            ndir = (di, dj)
            extra = turn_penalty if (pdir is not None and ndir != pdir) else 0.0
            ng = g + step + extra
            nstate = (n, ndir)
            if ng < best.get(nstate, math.inf):
                best[nstate] = ng
                came_from[nstate] = state
                nf = ng + _octile(n, goal_ij)
                heapq.heappush(open_heap, (nf, next(counter), ng, nstate))

    return None

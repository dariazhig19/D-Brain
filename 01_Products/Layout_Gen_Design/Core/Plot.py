"""Plot — convex polygon plot boundary (≤6 edges) for PowerPlan AI.

Phase 06 polygon migration. Generalises the former rectangular plot, which the
engine represented as a bare ``(sw, sl)`` pair with an implicit origin at
``(0, 0)``. A rectangle is just a 4-vertex convex polygon, so
``Plot.rectangle(sw, sl)`` reproduces the legacy behaviour *exactly* — that
equivalence is locked by the golden test in ``tests/test_plot.py`` and is the
regression baseline for the whole migration.

Conventions
-----------
* Vertices are stored counter-clockwise (CCW). The constructor reorders a CW
  input automatically.
* For a CCW polygon, the **inward** normal of an edge ``p1→p2`` (direction
  ``d = (dx, dy)``) is the left normal ``(-dy, dx)`` normalised — it points into
  the interior.
* "Signed distance" of a point to an edge line = ``dot(point - p1,
  inward_normal)``. It is **positive inside**, zero on the edge, negative
  outside. A point is inside the convex polygon iff this is ``>= 0`` for every
  edge. The ``tol`` argument shifts every edge line outward by ``tol`` metres,
  matching the engine's three-pass boundary tolerance.

This module is pure geometry — no NumPy, no engine imports — so it ports cleanly
to a future C#/PyRevit add-in.
"""

import math

__all__ = ["Plot"]


def _line_intersection(p1, d1, p2, d2):
    """Intersection of line (p1 + t*d1) and (p2 + s*d2). Returns None if parallel."""
    (x1, y1), (dx1, dy1) = p1, d1
    (x2, y2), (dx2, dy2) = p2, d2
    denom = dx1 * dy2 - dy1 * dx2
    if abs(denom) < 1e-12:
        return None
    t = ((x2 - x1) * dy2 - (y2 - y1) * dx2) / denom
    return (x1 + t * dx1, y1 + t * dy1)


class Plot:
    """A convex polygon plot boundary (3–6 vertices)."""

    def __init__(self, vertices):
        verts = [(float(x), float(y)) for x, y in vertices]
        if len(verts) < 3:
            raise ValueError(f"Plot needs >= 3 vertices, got {len(verts)}")
        # Drop a duplicated closing vertex if present.
        if len(verts) > 3 and _pt_eq(verts[0], verts[-1]):
            verts = verts[:-1]
        self.vertices = self._ensure_ccw(verts)
        self._build_edges()

    # ── Constructors ─────────────────────────────────────────────────────
    @classmethod
    def rectangle(cls, sw, sl, x0=0.0, y0=0.0):
        """Legacy rectangle — 4-vertex convex polygon. Golden-test baseline."""
        return cls([(x0, y0), (x0 + sw, y0), (x0 + sw, y0 + sl), (x0, y0 + sl)])

    # ── Setup helpers ────────────────────────────────────────────────────
    @staticmethod
    def _signed_area(verts):
        a = 0.0
        n = len(verts)
        for i in range(n):
            x1, y1 = verts[i]
            x2, y2 = verts[(i + 1) % n]
            a += x1 * y2 - x2 * y1
        return a / 2.0

    def _ensure_ccw(self, verts):
        return verts if self._signed_area(verts) > 0 else list(reversed(verts))

    def _build_edges(self):
        """Build per-edge records: p1, p2, unit direction, inward unit normal, length."""
        self.edges = []
        n = len(self.vertices)
        for i in range(n):
            p1 = self.vertices[i]
            p2 = self.vertices[(i + 1) % n]
            dx, dy = p2[0] - p1[0], p2[1] - p1[1]
            length = math.hypot(dx, dy)
            if length < 1e-9:
                continue  # skip degenerate edge
            ux, uy = dx / length, dy / length
            # CCW interior is to the LEFT of the edge direction → inward = (-uy, ux).
            nx, ny = -uy, ux
            self.edges.append({
                "p1": p1, "p2": p2,
                "dir": (ux, uy), "normal": (nx, ny), "length": length,
            })

    # ── Bounding box / size (the legacy sw, sl substitute) ────────────────
    @property
    def bbox(self):
        xs = [v[0] for v in self.vertices]
        ys = [v[1] for v in self.vertices]
        return (min(xs), min(ys), max(xs), max(ys))

    @property
    def size(self):
        """(width, length) of the axis-aligned bounding box — the sw, sl analogue."""
        minx, miny, maxx, maxy = self.bbox
        return (maxx - minx, maxy - miny)

    @property
    def centroid(self):
        """Area centroid of the polygon."""
        n = len(self.vertices)
        a = 0.0
        cx = cy = 0.0
        for i in range(n):
            x1, y1 = self.vertices[i]
            x2, y2 = self.vertices[(i + 1) % n]
            cross = x1 * y2 - x2 * y1
            a += cross
            cx += (x1 + x2) * cross
            cy += (y1 + y2) * cross
        a *= 0.5
        if abs(a) < 1e-9:  # degenerate → fall back to vertex mean
            return (sum(v[0] for v in self.vertices) / n,
                    sum(v[1] for v in self.vertices) / n)
        return (cx / (6 * a), cy / (6 * a))

    # ── Containment ──────────────────────────────────────────────────────
    @staticmethod
    def _point_to_segment_dist(x, y, p1, p2):
        x1, y1 = p1
        x2, y2 = p2
        dx, dy = x2 - x1, y2 - y1
        l2 = dx*dx + dy*dy
        if l2 < 1e-9:
            return math.hypot(x - x1, y - y1)
        t = ((x - x1) * dx + (y - y1) * dy) / l2
        t = max(0.0, min(1.0, t))
        px = x1 + t * dx
        py = y1 + t * dy
        return math.hypot(x - px, y - py)

    def _dist_to_boundary(self, x, y):
        n = len(self.vertices)
        return min(self._point_to_segment_dist(x, y, self.vertices[i], self.vertices[(i+1)%n]) for i in range(n))

    def _edge_signed_dist(self, edge, x, y):
        nx, ny = edge["normal"]
        px, py = edge["p1"]
        return (x - px) * nx + (y - py) * ny  # >0 interior side

    def contains_point(self, x, y, tol=0.0):
        """True if (x, y) is inside the polygon expanded outward by ``tol`` metres.
        Uses general raycasting to support both convex and concave polygons correctly."""
        n = len(self.vertices)
        inside = False
        p1x, p1y = self.vertices[0]
        for i in range(n + 1):
            p2x, p2y = self.vertices[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
            
        if abs(tol) < 1e-9:
            return inside
            
        d = self._dist_to_boundary(x, y)
        if tol > 0.0:
            return inside or (d <= tol)
        else:
            return inside and (d >= -tol)

    def contains_rect(self, x, y, w, h, tol=0.0):
        """True if the AABB [x, x+w] × [y, y+h] is inside the polygon (+tol).
        A rectangle is fully inside iff all four corners are inside."""
        return (self.contains_point(x,     y,     tol) and
                self.contains_point(x + w, y,     tol) and
                self.contains_point(x + w, y + h, tol) and
                self.contains_point(x,     y + h, tol))

    def signed_dist_to_boundary(self, x, y):
        """Min signed distance from a point to the boundary.
        Positive inside, negative outside. Correctly supports concave polygons."""
        n = len(self.vertices)
        inside = False
        p1x, p1y = self.vertices[0]
        for i in range(n + 1):
            p2x, p2y = self.vertices[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
            
        d = self._dist_to_boundary(x, y)
        return d if inside else -d

    # ── Edge addressing (anchors / gate fallback) ────────────────────────
    def edge_point(self, idx, ratio, offset=0.0):
        """Point at ``ratio`` along edge ``idx`` (0..n-1), pushed inward by ``offset``.

        Generalises ``place_anchor``/``compute_gate``: with a rectangle and the
        right edge index this reproduces the N/S/E/W edge placement.
        """
        e = self.edges[idx % len(self.edges)]
        (x1, y1), (x2, y2) = e["p1"], e["p2"]
        px = x1 + ratio * (x2 - x1)
        py = y1 + ratio * (y2 - y1)
        nx, ny = e["normal"]
        return (px + offset * nx, py + offset * ny)

    def nearest_edge(self, x, y):
        """Index of the edge whose line is closest to the point."""
        return min(range(len(self.edges)),
                   key=lambda i: abs(self._edge_signed_dist(self.edges[i], x, y)))

    # ── Geometry transforms ──────────────────────────────────────────────
    def translate(self, dx, dy):
        return Plot([(x + dx, y + dy) for x, y in self.vertices])

    def inset(self, d):
        """Return the convex polygon with every edge shifted inward by ``d`` metres.

        Used by the perimeter fire road (§3.7): each edge line moves inward
        along its normal by ``d``; new vertices are the intersections of adjacent
        shifted edge lines. Replaces the rectangle-only ``build_perimeter_road``.
        """
        n = len(self.edges)
        shifted = []  # (point_on_shifted_line, direction)
        for e in self.edges:
            nx, ny = e["normal"]
            p1 = (e["p1"][0] + d * nx, e["p1"][1] + d * ny)
            shifted.append((p1, e["dir"]))
        new_verts = []
        for i in range(n):
            prev = shifted[(i - 1) % n]
            cur = shifted[i]
            pt = _line_intersection(prev[0], prev[1], cur[0], cur[1])
            if pt is not None:
                new_verts.append(pt)
        return Plot(new_verts)

    # ── Rasterisation (grid / perimeter clamp) ───────────────────────────
    def cell_inside_mask(self, ncols, nrows, cell_size, origin=(0.0, 0.0)):
        """Boolean mask [ncols][nrows]: True where the cell *centre* is inside.

        Used to mark grid cells outside the polygon as blocked (rack routing) and
        to clamp the perimeter flood-fill to the polygon interior.
        """
        ox, oy = origin
        mask = [[False] * nrows for _ in range(ncols)]
        for i in range(ncols):
            cx = ox + (i + 0.5) * cell_size
            for j in range(nrows):
                cy = oy + (j + 0.5) * cell_size
                mask[i][j] = self.contains_point(cx, cy)
        return mask

    def __repr__(self):
        return f"Plot({len(self.vertices)} verts, bbox={tuple(round(v,1) for v in self.bbox)})"


def _pt_eq(a, b, tol=1e-9):
    return abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol

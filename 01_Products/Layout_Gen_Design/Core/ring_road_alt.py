from .Layout06 import PB_RING_OFFSET, PERIMETER_ROAD_W

def build_pb_ring_road_alt(pb_x, pb_y, pb_w, pb_h, offset=PB_RING_OFFSET, inner_corner_width=18):
    """Return a polyline for the ring road where inner corners are widened to *inner_corner_width*.
    The outer rectangle matches the original ring road (offset from the PB bbox).
    Extra points are inserted at each corner to create a beveled thicker corner.
    """
    # Outer rectangle corners (counter‑clockwise)
    x1, y1 = pb_x - offset, pb_y - offset
    x2, y2 = pb_x + pb_w + offset, pb_y + pb_h + offset
    # Compute half of the extra width beyond the normal perimeter road width
    delta = (inner_corner_width - PERIMETER_ROAD_W) / 2.0
    # Build polyline with extra corner points (bottom‑left → bottom‑right → top‑right bevel → top‑right → top‑left bevel → …)
    pts = []
    # start bottom‑left, go right
    pts.append((x1, y1))
    pts.append((x2, y1))
    # top‑right corner bevel (push up by delta before turning left)
    pts.append((x2, y1 + delta))
    pts.append((x2, y2))
    # top‑left corner bevel (push left by delta before turning down)
    pts.append((x2 - delta, y2))
    pts.append((x1, y2))
    # bottom‑left corner bevel (push down by delta before closing)
    pts.append((x1, y2 - delta))
    pts.append((x1, y1))
    return pts

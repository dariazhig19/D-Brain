import sys, random, importlib, math
sys.path.append('.')
import Core.Layout06 as L
importlib.reload(L)

def test():
    random.seed(42)
    r = L.generate_sketch(
        500, 270, 'East',
        gate_side="N", gate_ratio=0.4,
        gh_edge="N", gh_ratio=0.6, gh_offset=15,
        bb_edge="N",
        gis_edge="N", gis_ratio=0.9, gis_offset=15,
        water_edge="E", water_ratio=0.2, water_offset=0
    )
    
    segs = r['all_segments_cleaned']
    raw_segs = r['group_a_segments_raw'] + r['perimeter_segments_raw']
    sw, sl = 500, 270
    TOL = 0.1

    h_segs = []
    v_segs = []
    for (ax, ay), (bx, by) in segs:
        if abs(ay - by) < TOL:
            h_segs.append((min(ax, bx), max(ax, bx), ay))
        elif abs(ax - bx) < TOL:
            v_segs.append((ax, min(ay, by), max(ay, by)))

    raw_h = set()
    raw_v = set()
    for (ax, ay), (bx, by) in raw_segs:
        if abs(ay - by) < TOL:
            raw_h.add((round(min(ax, bx), 1), round(max(ax, bx), 1), round(ay, 1)))
        elif abs(ax - bx) < TOL:
            raw_v.add((round(ax, 1), round(min(ay, by), 1), round(max(ay, by), 1)))

    def _is_original_h(x0, x1, y):
        return (round(x0, 1), round(x1, 1), round(y, 1)) in raw_h

    def _is_original_v(x, y0, y1):
        return (round(x, 1), round(y0, 1), round(y1, 1)) in raw_v

    def _x_ranges_overlap(ax0, ax1, bx0, bx1):
        return min(ax1, bx1) > max(ax0, bx0)

    def _y_ranges_overlap(ay0, ay1, by0, by1):
        return min(ay1, by1) > max(ay0, by0)

    outer_n, outer_s, outer_e, outer_w = [], [], [], []
    for h in h_segs:
        hx0, hx1, hy = h
        if not _is_original_h(hx0, hx1, hy): continue
        is_n = not any(h2[2] > hy + TOL and _x_ranges_overlap(hx0, hx1, h2[0], h2[1]) for h2 in h_segs)
        is_s = not any(h2[2] < hy - TOL and _x_ranges_overlap(hx0, hx1, h2[0], h2[1]) for h2 in h_segs)
        if is_n: outer_n.append(('N', h))
        if is_s: outer_s.append(('S', h))
    for v in v_segs:
        vx, vy0, vy1 = v
        if not _is_original_v(vx, vy0, vy1): continue
        is_e = not any(v2[0] > vx + TOL and _y_ranges_overlap(vy0, vy1, v2[1], v2[2]) for v2 in v_segs)
        is_w = not any(v2[0] < vx - TOL and _y_ranges_overlap(vy0, vy1, v2[1], v2[2]) for v2 in v_segs)
        if is_e: outer_e.append(('E', v))
        if is_w: outer_w.append(('W', v))

    unused = outer_n + outer_s + outer_e + outer_w

    def ray_hit(ray_pt, ray_dir, targets_h, targets_v):
        px, py = ray_pt
        dx, dy = ray_dir
        best_dist = float('inf')
        best_pt = None
        best_seg = None
        for h in targets_h:
            x0, x1, y = h
            if dx == 0 and dy != 0:
                if (dy > 0 and y > py + TOL) or (dy < 0 and y < py - TOL):
                    if x0 - TOL <= px <= x1 + TOL:
                        d = abs(y - py)
                        if d < best_dist:
                            best_dist = d; best_pt = (px, y); best_seg = h
            elif dx != 0 and dy == 0:
                if abs(y - py) < TOL:
                    if dx > 0 and x0 > px + TOL:
                        d = x0 - px
                        if d < best_dist:
                            best_dist = d; best_pt = (x0, y); best_seg = h
                    elif dx < 0 and x1 < px - TOL:
                        d = px - x1
                        if d < best_dist:
                            best_dist = d; best_pt = (x1, y); best_seg = h
        for v in targets_v:
            x, y0, y1 = v
            if dy == 0 and dx != 0:
                if (dx > 0 and x > px + TOL) or (dx < 0 and x < px - TOL):
                    if y0 - TOL <= py <= y1 + TOL:
                        d = abs(x - px)
                        if d < best_dist:
                            best_dist = d; best_pt = (x, py); best_seg = v
            elif dx == 0 and dy != 0:
                if abs(x - px) < TOL:
                    if dy > 0 and y0 > py + TOL:
                        d = y0 - py
                        if d < best_dist:
                            best_dist = d; best_pt = (x, y0); best_seg = v
                    elif dy < 0 and y1 < py - TOL:
                        d = py - y1
                        if d < best_dist:
                            best_dist = d; best_pt = (x, y1); best_seg = v
        return best_pt, best_seg

    # Sort to find starting point
    if not outer_n: return
    outer_n.sort(key=lambda item: item[1][2], reverse=True)
    current = outer_n[0]
    start_kind, start_seg = current
    
    # Starting base point: left end of top-most North segment.
    # Actually wait: The start point is the right end of the top-most N segment.
    start_pt = (start_seg[1], start_seg[2]) # x1, y
    
    connectors = []
    
    def l_shape(p1, p2):
        # Draw L-shape from p1 to p2.
        # It's an axis aligned path. Which axis first?
        # Typically if p1 and p2 are on walls, we draw along the wall.
        # But this function is just a generic helper to make sure we don't draw diagonals.
        pass

    # Better logic:
    # Rule C (or Rule B traveling):
    # We are at `pt`. We need to reach `target_pt` (which is the start of `target_seg`).
    # We must travel axis aligned.
    def get_clock_dir(kind):
        if kind == 'N': return (1, 0)
        if kind == 'E': return (0, -1)
        if kind == 'S': return (-1, 0)
        if kind == 'W': return (0, 1)

    # Let's write the routing helper
    def route_axis_aligned(p1, p2):
        # returns list of points (p1, corner, p2)
        if abs(p1[0]-p2[0]) < TOL or abs(p1[1]-p2[1]) < TOL:
            return [(p1, p2)]
        # We need to decide the corner.
        # If we are traveling along N wall (horizontal), we should go horizontal first, then vertical.
        # This will form an L shape.
        return [(p1, (p2[0], p1[1])), ((p2[0], p1[1]), p2)]

    # Main Loop
    for step in range(50):
        if current in unused:
            unused.remove(current)
        kind, seg = current
        
        if kind == 'N':
            ray_pt = (seg[1], seg[2]) # RIGHT end
            ray_dir = (1, 0)
        elif kind == 'E':
            ray_pt = (seg[0], seg[1]) # BOTTOM end
            ray_dir = (0, -1)
        elif kind == 'S':
            ray_pt = (seg[0], seg[2]) # LEFT end
            ray_dir = (-1, 0)
        elif kind == 'W':
            ray_pt = (seg[0], seg[2]) # TOP end
            ray_dir = (0, 1)

        print(f"Step {step}: Current {kind} {seg}, ray from {ray_pt} dir {ray_dir}")
        
        unused_h = [s[1] for s in unused if s[0] in ('N', 'S')]
        unused_v = [s[1] for s in unused if s[0] in ('E', 'W')]
        
        hit_pt1, hit_seg1 = ray_hit(ray_pt, ray_dir, unused_h, unused_v)
        hit_pt2, hit_seg2 = ray_hit(ray_pt, ray_dir, h_segs, v_segs)
        
        d1 = math.hypot(ray_pt[0]-hit_pt1[0], ray_pt[1]-hit_pt1[1]) if hit_pt1 else float('inf')
        d2 = math.hypot(ray_pt[0]-hit_pt2[0], ray_pt[1]-hit_pt2[1]) if hit_pt2 else float('inf')
        
        if hit_pt1 and d1 <= d2:
            print(f"  -> Rule A Hit: unused {hit_seg1}")
            connectors.append((ray_pt, hit_pt1))
            for u in unused:
                if u[1] == hit_seg1:
                    current = u
                    break
        elif hit_pt2 and hit_seg2:
            print(f"  -> Rule B Hit: cleaned {hit_seg2}")
            connectors.append((ray_pt, hit_pt2))
            
            # Find closest unused
            best_dist = float('inf')
            best_u = None
            best_target_pt = None
            for u in unused:
                ukind, useg = u
                if ukind == 'N': upt = (useg[0], useg[2]) # target is the START (left) of the next segment
                elif ukind == 'E': upt = (useg[0], useg[2]) # target is TOP end
                elif ukind == 'S': upt = (useg[1], useg[2]) # target is RIGHT end
                elif ukind == 'W': upt = (useg[0], useg[1]) # target is BOTTOM end
                
                dist = math.hypot(hit_pt2[0]-upt[0], hit_pt2[1]-upt[1])
                if dist < best_dist:
                    best_dist = dist
                    best_u = u
                    best_target_pt = upt
            
            if not best_u:
                break
            
            # Draw axis aligned from hit_pt2 to best_target_pt
            for pA, pB in route_axis_aligned(hit_pt2, best_target_pt):
                connectors.append((pA, pB))
            current = best_u
            
        else:
            print("  -> Rule C: No hit.")
            # find closest unused
            best_dist = float('inf')
            best_u = None
            best_target_pt = None
            for u in unused:
                ukind, useg = u
                if ukind == 'N': upt = (useg[0], useg[2])
                elif ukind == 'E': upt = (useg[0], useg[2])
                elif ukind == 'S': upt = (useg[1], useg[2])
                elif ukind == 'W': upt = (useg[0], useg[1])
                
                dist = math.hypot(ray_pt[0]-upt[0], ray_pt[1]-upt[1])
                if dist < best_dist:
                    best_dist = dist
                    best_u = u
                    best_target_pt = upt
            
            if not best_u:
                break
                
            for pA, pB in route_axis_aligned(ray_pt, best_target_pt):
                connectors.append((pA, pB))
            current = best_u

        if not unused:
            # Loop closure
            print("  -> Closing loop to start")
            # Connect ray_pt of last to start_base
            last_ray_pt = None
            if current[0] == 'N': last_ray_pt = (current[1][1], current[1][2])
            elif current[0] == 'E': last_ray_pt = (current[1][0], current[1][1])
            elif current[0] == 'S': last_ray_pt = (current[1][0], current[1][2])
            elif current[0] == 'W': last_ray_pt = (current[1][0], current[1][2])
            
            # The start base is the starting point of start_seg
            start_base = (start_seg[0], start_seg[2])
            for pA, pB in route_axis_aligned(last_ray_pt, start_base):
                connectors.append((pA, pB))
            break
            
    print("Done! Connectors:", len(connectors))

if __name__ == "__main__":
    test()

import sys, os, random, math
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Core.Layout06 import generate_sketch
from Core.Grid import Grid
from Core.Pathfind import astar

def get_line_points(p1, p2, step=2.0):
    """Sample points along a line segment from p1 to p2 every `step` meters."""
    x1, y1 = p1
    x2, y2 = p2
    dx = x2 - x1
    dy = y2 - y1
    dist = math.sqrt(dx*dx + dy*dy)
    if dist < 0.001:
        return [p1]
    points = []
    n_steps = int(math.ceil(dist / step))
    for s in range(n_steps + 1):
        t = s / n_steps
        points.append((x1 + dx * t, y1 + dy * t))
    return points

def find_nearest_road_point(block_center, road_polyline):
    """Find the point along the road polyline closest to block_center."""
    cx, cy = block_center
    best_pt = None
    best_dist = math.inf
    # Traverse each segment of the polyline
    for i in range(len(road_polyline) - 1):
        pts = get_line_points(road_polyline[i], road_polyline[i+1], step=2.0)
        for rx, ry in pts:
            d = (rx - cx)**2 + (ry - cy)**2
            if d < best_dist:
                best_dist = d
                best_pt = (rx, ry)
    return best_pt

def get_block_candidates(b, sw, sl):
    """Get the 4 outer midpoints of a block (North, South, East, West)."""
    bx, by, bw, bh = b['x'], b['y'], b['width'], b['height']
    cx, cy = bx + bw/2, by + bh/2
    candidates = [
        (cx, by + bh + 2), # North
        (cx, by - 2),      # South
        (bx + bw + 2, cy), # East
        (bx - 2, cy),      # West
    ]
    # Clamp candidates to site bounds
    valid = []
    for x, y in candidates:
        x = max(2, min(sw - 2, x))
        y = max(2, min(sl - 2, y))
        valid.append((x, y))
    return valid

# Generate a sketch
random.seed(42)
r = generate_sketch(500, 270, 'East')

if r:
    print("LAYOUT SUCCESSFULLY GENERATED")
    blocks = r['blocks']
    ring = r['ring_road']
    perimeter = r['perimeter_road']
    sw, sl = 500, 270
    
    grid = Grid(sw, sl, cell_size=2)
    # Mark all blocks as blocked
    for b in blocks:
        grid.mark_building(b, inflate_m=0)
        
    # Route stubs for each block (except Gate House)
    for b in blocks:
        if b['name'] == 'Gate House':
            continue
        
        bx, by, bw, bh = b['x'], b['y'], b['width'], b['height']
        bc = (bx + bw/2, by + bh/2)
        
        # 1. Closest points on road centerlines
        pt_ring = find_nearest_road_point(bc, ring)
        pt_peri = find_nearest_road_point(bc, perimeter)
        
        # 2. Block candidates
        candidates = get_block_candidates(b, sw, sl)
        
        print(f"\nBlock: {b['name']}")
        print(f"  Ring road goal: {pt_ring}")
        print(f"  Perimeter road goal: {pt_peri}")
        
        # Let's try to find an A* path for each
        for road_name, goal_pt in [("Ring Road", pt_ring), ("Perimeter Road", pt_peri)]:
            # Find the best candidate start cell
            best_path = None
            best_cost = math.inf
            goal_cell = grid.world_to_cell(*goal_pt)
            
            # Since the goal itself might be occupied if it sits exactly on a block boundary,
            # let's temporarily free the start candidates and goal cell in the grid so A* can route!
            for cx, cy in candidates:
                start_cell = grid.world_to_cell(cx, cy)
                
                # Temporarily free cells for A* search
                was_blocked_start = grid.blocked[start_cell]
                was_blocked_goal = grid.blocked[goal_cell]
                grid.blocked[start_cell] = False
                grid.blocked[goal_cell] = False
                
                path = astar(grid, start_cell, goal_cell, width_cells=0)
                
                # Restore occupancy
                grid.blocked[start_cell] = was_blocked_start
                grid.blocked[goal_cell] = was_blocked_goal
                
                if path:
                    cost = len(path)
                    if cost < best_cost:
                        best_cost = cost
                        best_path = path
            
            if best_path:
                # Convert path cells back to world coordinates
                world_path = [grid.cell_to_world(*c) for c in best_path]
                print(f"  -> Path to {road_name}: FOUND ({len(world_path)} cells, start={world_path[0]}, end={world_path[-1]})")
            else:
                # Fallback: direct line from closest candidate to goal
                closest_cand = min(candidates, key=lambda c: (c[0]-goal_pt[0])**2 + (c[1]-goal_pt[1])**2)
                fallback_path = [closest_cand, goal_pt]
                print(f"  -> Path to {road_name}: FAILED (Fallback straight path, len=2)")
                
else:
    print("FAILED")

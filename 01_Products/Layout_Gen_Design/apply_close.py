import re

with open("Core/Layout06.py", "r", encoding="utf-8") as f:
    code = f.read()

new_logic = """
def compute_buffer_union_contour(computed_buffers):
    FIRE_ROAD_BLOCKS = {"WT/WWT", "RAW Water Tank", "Cooling Tower", "Warehouse", "GIS", "Admin Building", "Power Block"}
    filtered_buffers = {name: b for name, b in computed_buffers.items() if name in FIRE_ROAD_BLOCKS}
    
    TOL = 0.1
    if not filtered_buffers: return [], {}
    
    # 1. Base grid bounds
    min_x = min(b[0] for b in filtered_buffers.values())
    min_y = min(b[1] for b in filtered_buffers.values())
    max_x = max(b[0] + b[2] for b in filtered_buffers.values())
    max_y = max(b[1] + b[3] for b in filtered_buffers.values())
    
    RES = 0.5
    K_m = 30 # 30m closing radius -> bridges gaps up to 60m
    K = int(K_m / RES)
    
    # Pad grid by K + 5 cells to prevent morphological edge effects
    min_x -= (K_m + 5)
    min_y -= (K_m + 5)
    max_x += (K_m + 5)
    max_y += (K_m + 5)
    
    w_cells = int((max_x - min_x) / RES)
    h_cells = int((max_y - min_y) / RES)
    grid = [[0]*w_cells for _ in range(h_cells)]
    
    # 2. Paint blocks
    for name, (bx, by, bw, bh) in filtered_buffers.items():
        if name.startswith("_"): continue
        ix0, iy0 = int((bx - min_x) / RES), int((by - min_y) / RES)
        ix1, iy1 = int((bx + bw - min_x) / RES), int((by + bh - min_y) / RES)
        for y in range(max(0,iy0), min(h_cells,iy1)):
            for x in range(max(0,ix0), min(w_cells,ix1)):
                grid[y][x] = 1

    # 3. Morphological Closing (Dilate -> Erode)
    # Dilate
    d_grid = [[0]*w_cells for _ in range(h_cells)]
    for y in range(h_cells):
        count = 0
        for x in range(w_cells):
            if grid[y][x]: count = K + 1
            elif count > 0: count -= 1
            if count > 0: d_grid[y][x] = 1
        count = 0
        for x in range(w_cells-1, -1, -1):
            if grid[y][x]: count = K + 1
            elif count > 0: count -= 1
            if count > 0: d_grid[y][x] = 1
            
    d2_grid = [[0]*w_cells for _ in range(h_cells)]
    for x in range(w_cells):
        count = 0
        for y in range(h_cells):
            if d_grid[y][x]: count = K + 1
            elif count > 0: count -= 1
            if count > 0: d2_grid[y][x] = 1
        count = 0
        for y in range(h_cells-1, -1, -1):
            if d_grid[y][x]: count = K + 1
            elif count > 0: count -= 1
            if count > 0: d2_grid[y][x] = 1
            
    # Erode (Dilate the 0s)
    e_grid = [[1]*w_cells for _ in range(h_cells)]
    for y in range(h_cells):
        count = 0
        for x in range(w_cells):
            if not d2_grid[y][x]: count = K + 1
            elif count > 0: count -= 1
            if count > 0: e_grid[y][x] = 0
        count = 0
        for x in range(w_cells-1, -1, -1):
            if not d2_grid[y][x]: count = K + 1
            elif count > 0: count -= 1
            if count > 0: e_grid[y][x] = 0
            
    e2_grid = [[1]*w_cells for _ in range(h_cells)]
    for x in range(w_cells):
        count = 0
        for y in range(h_cells):
            if not e_grid[y][x]: count = K + 1
            elif count > 0: count -= 1
            if count > 0: e2_grid[y][x] = 0
        count = 0
        for y in range(h_cells-1, -1, -1):
            if not e_grid[y][x]: count = K + 1
            elif count > 0: count -= 1
            if count > 0: e2_grid[y][x] = 0
            
    # 4. Contour Tracing (Flood fill from outside)
    visited = set()
    # To avoid recursion limit, use a stack
    stack = [(0, 0)]
    visited.add((0, 0))
    while stack:
        cx, cy = stack.pop()
        for nx, ny in [(cx+1,cy), (cx-1,cy), (cx,cy+1), (cx,cy-1)]:
            if 0 <= nx < w_cells and 0 <= ny < h_cells:
                if e2_grid[ny][nx] == 0 and (nx, ny) not in visited:
                    visited.add((nx, ny))
                    stack.append((nx, ny))
                    
    edges = set()
    def is_outside(cx, cy):
        if cx < 0 or cx >= w_cells or cy < 0 or cy >= h_cells: return True
        return (cx, cy) in visited

    for y in range(h_cells):
        for x in range(w_cells):
            if not is_outside(x, y):
                if is_outside(x, y-1): edges.add(((x, y), (x+1, y)))
                if is_outside(x, y+1): edges.add(((x, y+1), (x+1, y+1)))
                if is_outside(x-1, y): edges.add(((x, y), (x, y+1)))
                if is_outside(x+1, y): edges.add(((x+1, y), (x+1, y+1)))
                
    real_edges = []
    for ((x1, y1), (x2, y2)) in edges:
        rx1, ry1 = min_x + x1*RES, min_y + y1*RES
        rx2, ry2 = min_x + x2*RES, min_y + y2*RES
        real_edges.append(((rx1, ry1), (rx2, ry2)))
        
    merged = []
    h_edges = [(min(e[0][0],e[1][0]), max(e[0][0],e[1][0]), e[0][1]) for e in real_edges if abs(e[0][1]-e[1][1]) < TOL]
    h_edges.sort(key=lambda x: (x[2], x[0]))
    if h_edges:
        cur_x0, cur_x1, cur_y = h_edges[0]
        for x0, x1, y in h_edges[1:]:
            if abs(y - cur_y) < TOL and x0 <= cur_x1 + TOL:
                cur_x1 = max(cur_x1, x1)
            else:
                merged.append(((cur_x0, cur_y), (cur_x1, cur_y)))
                cur_x0, cur_x1, cur_y = x0, x1, y
        merged.append(((cur_x0, cur_y), (cur_x1, cur_y)))
        
    v_edges = [(min(e[0][1],e[1][1]), max(e[0][1],e[1][1]), e[0][0]) for e in real_edges if abs(e[0][0]-e[1][0]) < TOL]
    v_edges.sort(key=lambda y: (y[2], y[0]))
    if v_edges:
        cur_y0, cur_y1, cur_x = v_edges[0]
        for y0, y1, x in v_edges[1:]:
            if abs(x - cur_x) < TOL and y0 <= cur_y1 + TOL:
                cur_y1 = max(cur_y1, y1)
            else:
                merged.append(((cur_x, cur_y0), (cur_x, cur_y1)))
                cur_y0, cur_y1, cur_x = y0, y1, x
        merged.append(((cur_x, cur_y0), (cur_x, cur_y1)))
        
    return merged, {"N":[], "S":[], "E":[], "W":[]}
"""

code = re.sub(r"def compute_buffer_union_contour\(computed_buffers\):.*?return merged, \{\"N\":\[\], \"S\":\[\], \"E\":\[\], \"W\":\[\]\}", new_logic, code, flags=re.DOTALL)

with open("Core/Layout06.py", "w", encoding="utf-8") as f:
    f.write(code)
    
print("Updated contour logic.")

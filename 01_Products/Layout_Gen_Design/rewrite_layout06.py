import re

with open("Core/Layout06.py", "r", encoding="utf-8") as f:
    code = f.read()

# 1. Remove build_outer_loop_pointwise
# It starts at `def build_outer_loop_pointwise` and ends before `def build_perimeter_road`
code = re.sub(r"def build_outer_loop_pointwise.*?def build_perimeter_road", 
              "def build_perimeter_road", code, flags=re.DOTALL)

# 2. Remove compute_snapped_buffers and generate_perimeter_segments
# They start at `def compute_snapped_buffers` and end before `def generate_group_a_access`
code = re.sub(r"def compute_snapped_buffers.*?def generate_group_a_access",
              "def generate_group_a_access", code, flags=re.DOTALL)

# 3. Add compute_buffer_union_contour where build_outer_loop_pointwise used to be
contour_code = """
def compute_unsnapped_buffers(placed):
    buffers = {}
    for name, bounds in placed.items():
        if name.startswith("_"): continue
        offset = 16 if name in RACK_BLOCKS else 8
        x, y, w, h = bounds
        buffers[name] = (x - offset, y - offset, w + 2*offset, h + 2*offset)
    return buffers

def compute_buffer_union_contour(computed_buffers):
    TOL = 0.1
    if not computed_buffers: return []
    min_x = min(b[0] for b in computed_buffers.values()) - 5
    min_y = min(b[1] for b in computed_buffers.values()) - 5
    max_x = max(b[0] + b[2] for b in computed_buffers.values()) + 5
    max_y = max(b[1] + b[3] for b in computed_buffers.values()) + 5
    
    RES = 0.5
    w_cells = int((max_x - min_x) / RES)
    h_cells = int((max_y - min_y) / RES)
    grid = [[0]*w_cells for _ in range(h_cells)]
    
    for name, (bx, by, bw, bh) in computed_buffers.items():
        if name.startswith("_"): continue
        ix0, iy0 = int((bx - min_x) / RES), int((by - min_y) / RES)
        ix1, iy1 = int((bx + bw - min_x) / RES), int((by + bh - min_y) / RES)
        for y in range(max(0,iy0), min(h_cells,iy1)):
            for x in range(max(0,ix0), min(w_cells,ix1)):
                grid[y][x] = 1

    visited = set()
    stack = [(0, 0)]
    visited.add((0, 0))
    while stack:
        cx, cy = stack.pop()
        for nx, ny in [(cx+1,cy), (cx-1,cy), (cx,cy+1), (cx,cy-1)]:
            if 0 <= nx < w_cells and 0 <= ny < h_cells:
                if grid[ny][nx] == 0 and (nx, ny) not in visited:
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

def build_perimeter_road"""
code = code.replace("def build_perimeter_road", contour_code)

# 4. In generate_sketch, replace the calls.
old_calls = """        computed_buffers = compute_snapped_buffers(placed)                                          # → §3.7.A
        perimeter_segments_raw = generate_perimeter_segments(computed_buffers, pb_cx, pb_cy)       # → §3.7.B

        group_a_segments_raw = generate_group_a_access(computed_buffers, placed, sw, sl, gate_pt[0], gate_pt[1])  # → §3.7.C · §3.8.B

        # B-2 Clean up parallel segments on both A-2 and B-1
        all_segments_raw = perimeter_segments_raw + group_a_segments_raw
        
        # Extract PB Ring Road network (Ring road + Gate spur + Ring spur) for Priority 1 matching
        pb_network = []
        if ring_road:
            for i in range(len(ring_road) - 1):
                pb_network.append((ring_road[i], ring_road[i+1]))
            pb_network.append((ring_road[-1], ring_road[0]))
        if gate_spur:
            for i in range(len(gate_spur) - 1):
                pb_network.append((gate_spur[i], gate_spur[i+1]))
        if ring_spur:
            for i in range(len(ring_spur) - 1):
                pb_network.append((ring_spur[i], ring_spur[i+1]))
                
        all_segments_cleaned = cleanup_parallel_segments(all_segments_raw, sw, sl, computed_buffers, ref_segs=pb_network, tol=17.0, gdz=gate_death_zone, pb_cx=pb_cx)  # → §3.7.D

        spur_segs = []
        for _spur in (gate_spur, ring_spur):
            if _spur:
                for _i in range(len(_spur) - 1):
                    spur_segs.append((_spur[_i], _spur[_i + 1]))
        outer_loop, outer_loop_pts = build_outer_loop_pointwise(all_segments_cleaned, computed_buffers, blocks, sw, sl, ring_road=ring_road, spurs=spur_segs, gate_side=gate_side)  # → §3.7.E"""

new_calls = """        computed_buffers = compute_unsnapped_buffers(placed)
        perimeter_segments_raw = []
        group_a_segments_raw = generate_group_a_access(computed_buffers, placed, sw, sl, gate_pt[0], gate_pt[1])
        all_segments_raw = group_a_segments_raw
        
        pb_network = []
        if ring_road:
            for i in range(len(ring_road) - 1):
                pb_network.append((ring_road[i], ring_road[i+1]))
            pb_network.append((ring_road[-1], ring_road[0]))
        if gate_spur:
            for i in range(len(gate_spur) - 1):
                pb_network.append((gate_spur[i], gate_spur[i+1]))
        if ring_spur:
            for i in range(len(ring_spur) - 1):
                pb_network.append((ring_spur[i], ring_spur[i+1]))
                
        all_segments_cleaned = cleanup_parallel_segments(all_segments_raw, sw, sl, computed_buffers, ref_segs=pb_network, tol=17.0, gdz=gate_death_zone, pb_cx=pb_cx)

        outer_loop, outer_loop_pts = compute_buffer_union_contour(computed_buffers)"""

if old_calls in code:
    code = code.replace(old_calls, new_calls)
else:
    print("Warning: old_calls not found exactly. Falling back to regex.")
    code = re.sub(r"computed_buffers = compute_snapped_buffers\(placed\).*?outer_loop, outer_loop_pts = build_outer_loop_pointwise[^\n]+", new_calls, code, flags=re.DOTALL)

with open("Core/Layout06.py", "w", encoding="utf-8") as f:
    f.write(code)
print("Rewrite complete.")

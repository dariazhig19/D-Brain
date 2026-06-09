def dilate_erode(grid, w_cells, h_cells, K):
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
            
    return e2_grid

w, h = 40, 30
grid = [[0]*w for _ in range(h)]
# Block A
for y in range(10, 15):
    for x in range(5, 15): grid[y][x] = 1
# Block B
for y in range(10, 15):
    for x in range(25, 35): grid[y][x] = 1
# PB block at bottom
for y in range(20, 25):
    for x in range(10, 30): grid[y][x] = 1

res = dilate_erode(grid, w, h, 6)

# Spur from top to PB. Let's pretend Gate is at y=5.
# If we only cut from y=5 to y=20, it's enclosed by the blob (blob top is y=4)
spur_x = 20
for y in range(5, 20):
    res[y][spur_x] = 0

print("Enclosed cut (flood fill can't enter):")
for row in res: print("".join("X" if c else "." for c in row))

# Extend cut to boundary
for y in range(0, 5):
    res[y][spur_x] = 0

print("\nExtended cut (flood fill can enter):")
for row in res: print("".join("X" if c else "." for c in row))

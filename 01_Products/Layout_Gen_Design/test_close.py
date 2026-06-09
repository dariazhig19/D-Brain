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

w, h = 40, 20
grid = [[0]*w for _ in range(h)]
# Block A
for y in range(5, 10):
    for x in range(5, 15): grid[y][x] = 1
# Block B
for y in range(5, 10):
    for x in range(25, 35): grid[y][x] = 1
# PB block at bottom
for y in range(15, 20):
    for x in range(10, 30): grid[y][x] = 1

# Spur from top to PB
spur_x = 20
for y in range(0, 15):
    grid[y][spur_x] = 1

res = dilate_erode(grid, w, h, 6)

print("Closed without subtracting spur:")
for row in res: print("".join("X" if c else "." for c in row))

# Now subtract spur from the closed grid
for y in range(0, 15):
    res[y][spur_x] = 0

print("\nClosed with subtracted spur:")
for row in res: print("".join("X" if c else "." for c in row))

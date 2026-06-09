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

# We need a big grid so it doesn't touch the edges when K=6
w, h = 40, 20
grid = [[0]*w for _ in range(h)]
grid[10][10] = 1
grid[10][20] = 1

print("Original:")
for row in grid: print("".join("X" if c else "." for c in row))

res = dilate_erode(grid, w, h, 6)

print("\nClosed:")
for row in res: print("".join("X" if c else "." for c in row))


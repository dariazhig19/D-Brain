import sys, os, random
# Add the project root directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Core.Layout06 import generate_sketch
from Core.Grid import Grid
from Core.Pathfind import astar

random.seed(42)
r = generate_sketch(500, 270, 'East')

if r:
    print("SUCCESSFULLY GENERATED SKETCH LAYOUT")
    blocks = r['blocks']
    sw, sl = 500, 270
    grid = Grid(sw, sl, cell_size=2)
    
    # Mark all blocks as blocked
    for b in blocks:
        grid.mark_building(b, inflate_m=0)
        
    print(grid)
else:
    print("FAILED TO GENERATE SKETCH LAYOUT")

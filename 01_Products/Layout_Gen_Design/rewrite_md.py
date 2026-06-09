import re

with open(r"c:\Users\상상진화\Documents\GitHub\D-Brain\00_Input\Phase_06_Plan_Structured.md", "r", encoding="utf-8") as f:
    plan = f.read()

new_section = """### §3.7 Perimeter Fire Road (Union of Buffers Contour)

Instead of heuristic intersections, the perimeter fire road is generated mathematically by tracing the boolean union of all block road buffers.

#### §3.7.A Buffer Inflation
Each placed block is expanded outward by its required road offset:
- **Rack Blocks:** 16 m offset.
- **No-Rack Blocks:** 8 m offset.

This generates an axis-aligned buffer rectangle around every block.

#### §3.7.B Grid-Based Boolean Union
A high-resolution 2D integer grid is created over the plot bounds. The buffer rectangle of every block is "painted" onto this grid (setting cells to 1). This effectively performs a geometric boolean union of all required road stand-offs, forming a single continuous footprint.

#### §3.7.C Contour Tracing (The Perimeter Road)
A flood-fill algorithm runs from the outside of the grid to identify all "exterior" empty cells. 
The boundary edges between the exterior (empty) cells and the interior (filled) cells are extracted. These edges are merged into contiguous orthogonal line segments. 

The resulting polyline is mathematically guaranteed to be a closed, continuous, and non-intersecting loop that perfectly hugs the facility at the exact required stand-off distances (8m or 16m), forming the final **Outer Perimeter Loop**.

#### §3.7.D Group A — 8m Road Access Lines"""

plan = re.sub(r"### §3.7 Perimeter Fire Road.*?#### §3.7.C Group A — 8m Road Access Lines", new_section, plan, flags=re.DOTALL)

with open(r"c:\Users\상상진화\Documents\GitHub\D-Brain\00_Input\Phase_06_Plan_Structured.md", "w", encoding="utf-8") as f:
    f.write(plan)
    
print("Updated markdown.")

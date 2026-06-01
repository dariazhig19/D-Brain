### §3.7.E — Fire Perimeter Loop Closure (Clockwise Tracing)

**Goal:** Connect the outermost fire perimeter segments into a single continuous clockwise loop.

#### E-1. Identify Outer Segments
Find the outermost unswept segments for each plot side (same as before):
- **North outer segments:** Horizontal lines exposed to the top. (Clockwise = RIGHT)
- **East outer segments:** Vertical lines exposed to the right. (Clockwise = DOWN)
- **South outer segments:** Horizontal lines exposed to the bottom. (Clockwise = LEFT)
- **West outer segments:** Vertical lines exposed to the left. (Clockwise = UP)

#### E-2. Clockwise Loop Tracing
Start with the highest/leftmost **North outer segment**. We trace a continuous path clockwise.

At any given step, you have a **Current Segment**.
You extend its clockwise endpoint in the clockwise direction (e.g., North segment extends RIGHT).

**Intersection Rules (evaluated in order):**
1. **Hits another Outer Segment:** If the extension hits another Outer Segment (or the extension line of one), draw the connection. The hit segment becomes the new Current Segment. Change direction to match the new segment's clockwise direction.
2. **Hits an existing Cleaned Segment (belonging to an Outer Segment's block):** If the extension hits a normal `all_segments_cleaned` line, and that line belongs to the same block as an unused Outer Segment, draw the connection. That block's Outer Segment becomes the new Current Segment.
3. **No Intersection (Find Closest):** If the ray goes infinitely without hitting the above, stop. Find the *closest* unused Outer Segment that is either on the same plot side (further along) or on the *next* clockwise side (e.g., if extending RIGHT on North side, look for next North segment or first East segment). Draw a 90-degree connector (or straight line) connecting to it. That found segment becomes the new Current Segment.

Repeat this until you loop all the way back to the starting segment.

---
**Example Trace:**
1. Start at **CT top** (North outer). Extend RIGHT.
2. Hits **GIS left vertical** (Rule 2). GIS has an unused North outer segment (**GIS top**).
3. Switch Current Segment to **GIS top**. Extend RIGHT.
4. No hit (Rule 3). Closest unused is **GIS right** (East outer). Connect GIS top right-end to GIS right top-end.
5. Current Segment is **GIS right**. Extend DOWN.
6. ... and so on, continuing around the plot.

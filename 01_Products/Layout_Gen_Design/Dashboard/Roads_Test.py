"""Road debugging dashboard — Phase 05 & Phase 06 side-by-side test.

Run with:
    streamlit run 01_Products/Layout_Gen_Design/Dashboard/Roads_Test.py
"""

import streamlit as st
import sys, os, random
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import cm, colors as mcolors

import importlib
import Core.Groups, Core.Roads, Core.Rules, Core.Main, Core.Grid, Core.Pathfind, Core.Layout06
importlib.reload(Core.Grid)
importlib.reload(Core.Pathfind)
importlib.reload(Core.Groups)
importlib.reload(Core.Roads)
importlib.reload(Core.Rules)
importlib.reload(Core.Main)
importlib.reload(Core.Layout06)

from Core.Groups import draw_group, draw_rack, SHAPES
from Core.Rules import RULES
from Core.Main import generate_layouts
from Core.Roads import build_road_network
from Core.Layout06 import generate_sketch, CELL_SIZE, ROAD_BUFFER

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

st.set_page_config(page_title="Roads Test", layout="wide")

# ── Phase selector ─────────────────────────────────────────────────────────
phase = st.radio("Engine", ["Phase 05 (A* roads)", "Phase 06 (Sketch roads)"],
                 horizontal=True)

st.divider()

# ── Shared sidebar: site + gate ────────────────────────────────────────────
st.sidebar.header("Site")
site_width  = st.sidebar.slider("Plot Width (A)",  100, 1000, 500, step=10)
site_length = st.sidebar.slider("Plot Length (B)", 100, 1000, 270, step=10)
wind_dir    = st.sidebar.selectbox("Wind Direction",
                                   ["North", "South", "East", "West"], index=2)

st.sidebar.divider()
st.sidebar.header("Site Gate")
gate_side  = st.sidebar.selectbox("Gate edge", ["N", "S", "E", "W"], index=0)
gate_ratio = st.sidebar.slider("Gate position along edge", 0.1, 0.9, 0.5, step=0.05)

st.sidebar.divider()
st.sidebar.header("Fixed Anchors")
st.sidebar.subheader("Gate House")
gh_edge   = st.sidebar.selectbox("Edge (GH)",     ["N", "S", "E", "W"], index=0)
gh_ratio  = st.sidebar.slider("Position (GH)",    0.0, 1.0, 0.5, step=0.05)
gh_offset = st.sidebar.slider("Offset (GH)",      0, 50, 0, step=1)
bb_edge   = st.sidebar.selectbox("Boom Barrier Side (GH)", ["N", "S", "E", "W"], index=1)

st.sidebar.subheader("GIS")
gis_edge   = st.sidebar.selectbox("Edge (GIS)",   ["N", "S", "E", "W"], index=1)
gis_ratio  = st.sidebar.slider("Position (GIS)",  0.0, 1.0, 0.8, step=0.05)
gis_offset = st.sidebar.slider("Offset (GIS)",    0, 50, 0, step=1)

st.sidebar.subheader("RAW Water Tank")
water_edge   = st.sidebar.selectbox("Edge (RAW Water)", ["N", "S", "E", "W"], index=2)
water_ratio  = st.sidebar.slider("Position (RAW Water)", 0.0, 1.0, 0.2, step=0.05)
water_offset = st.sidebar.slider("Offset (RAW Water)",   0, 50, 0, step=1)

st.sidebar.divider()

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 06
# ══════════════════════════════════════════════════════════════════════════════
if phase == "Phase 06 (Sketch roads)":
    st.title("Phase 06 — Block + Road Sketch")
    st.markdown("Reference: [Phase 06 Plan](file:///x:/CST%EB%B3%B8%EB%B6%80%20%28%EA%B5%AC%20%EA%B8%B0%EC%88%A0%EC%A7%80%EC%9B%90%EB%B6%80%20%ED%8F%B4%EB%8D%94%29/15.%20%EB%8B%A4%EB%A6%AC%EC%95%84/D-Brain/00_Input/Phase_06_Plan.md)")
    st.caption("Steps 1.1–1.5: blocks · ring + perimeter fire roads · stubs · 2-path verification + pruning")

    st.sidebar.header("Phase 06 Settings")
    show_grid     = st.sidebar.checkbox("2m Grid lines", value=False)
    show_buffer       = st.sidebar.checkbox(f"Block {ROAD_BUFFER}m + 16m buffers (default)", value=True)
    show_rack_no_rack = st.sidebar.checkbox("Rack-block baseline buffers (8m / 16m)", value=False)
    show_rack_w_rack  = st.sidebar.checkbox("Rack-block w-rack buffers (Case 1 6m / road 14m / Case 2 22m / b2b 28m)", value=True)
    show_b1_perimeter = st.sidebar.checkbox("Show B-1 Perimeter Segments", value=False)
    show_a2_access    = st.sidebar.checkbox("Show A-2 Group A Access", value=True)
    show_legend   = st.sidebar.checkbox("Legend", value=True)
    fix_seed      = st.sidebar.checkbox("Fix seed", value=True)
    seed_val      = st.sidebar.number_input("Seed", 0, 10000, 42, disabled=not fix_seed)

    if st.button("Generate Sketch", type="primary", use_container_width=True):
        if fix_seed:
            random.seed(int(seed_val))
        with st.spinner("Generating Phase 06 sketch..."):
            sketch = generate_sketch(
                site_width, site_length, wind_dir,
                gate_side=gate_side, gate_ratio=gate_ratio,
                gh_edge=gh_edge,    gh_ratio=gh_ratio,    gh_offset=gh_offset,
                bb_edge=bb_edge,
                gis_edge=gis_edge,  gis_ratio=gis_ratio,  gis_offset=gis_offset,
                water_edge=water_edge, water_ratio=water_ratio, water_offset=water_offset,
            )
        if sketch is None:
            st.error("Could not place all blocks — try changing site size or parameters.")
        else:
            st.session_state["sketch06"] = sketch
            st.session_state["params06"] = (site_width, site_length)

    sketch = st.session_state.get("sketch06")
    if sketch is None:
        st.info("Set parameters in the sidebar, then click **Generate Sketch**.")
        st.stop()

    sw, sl = st.session_state.get("params06", (site_width, site_length))
    blocks        = sketch["blocks"]
    ring_road     = sketch["ring_road"]
    perimeter     = sketch.get("perimeter_segments", [])
    gate_pt       = sketch["gate_point"]
    pb_center     = sketch["pb_center"]

    fig, ax = plt.subplots(figsize=(13, 8), dpi=110)

    # Site fill + boundary
    ax.fill([0,sw,sw,0,0], [0,0,sl,sl,0], color='#f0f8ff', zorder=0)
    ax.plot([0,sw,sw,0,0], [0,0,sl,sl,0], color='black', lw=1.2, zorder=1)

    # 2m grid
    if show_grid:
        cs = CELL_SIZE
        for i in range(int(sw // cs) + 1):
            ax.axvline(i * cs, color='#dddddd', lw=0.2, zorder=0.1)
        for j in range(int(sl // cs) + 1):
            ax.axhline(j * cs, color='#dddddd', lw=0.2, zorder=0.1)

    if show_b1_perimeter:
        for k, ((x1, y1), (x2, y2)) in enumerate(perimeter):
            ax.plot([x1, x2], [y1, y2], color='#ffff00', lw=2.5, alpha=1.0, zorder=3.0,
                    solid_capstyle='round', label='Perimeter CL (raw)' if k == 0 else "")
    rx, ry = zip(*ring_road)
    ax.plot(rx, ry, color='#e91e8c', lw=2.5, alpha=0.95, zorder=2.5,
            solid_capstyle='round', label='A-1 PB Ring Road')
    # Gate spur (perimeter → gate point) — short primary segment
    gs = sketch.get("gate_spur") or []
    if len(gs) >= 2:
        gsx, gsy = zip(*gs)
        ax.plot(gsx, gsy, color='#e91e8c', lw=2.5, alpha=0.95, zorder=2.5,
                solid_capstyle='round', label='Gate spur')

    # A-2 Group A Access lines
    if show_a2_access:
        group_a = sketch.get("group_a_segments", [])
        for k, ((x1, y1), (x2, y2)) in enumerate(group_a):
            ax.plot([x1, x2], [y1, y2], color='#00ff00', lw=2.5, alpha=1.0, zorder=3.5,
                    solid_capstyle='round', label='Group A Access' if k == 0 else "")

    # Ring spur (ring → perimeter) — primary connector around blocks
    rs = sketch.get("ring_spur") or []
    if len(rs) >= 2:
        rsx, rsy = zip(*rs)
        ax.plot(rsx, rsy, color='#e91e8c', lw=2.5, alpha=0.95, zorder=2.5,
                solid_capstyle='round', label='Ring spur')

    # Default buffer halos per block (visualize the magnetic snap boundaries):
    #  - Rack blocks: 14m road buffer (so two rack blocks touching sit 28m apart)
    #  - No-rack blocks: 8m road buffer (so two no-rack touching sit 16m apart)
    if show_buffer:
        legended_buffers = set()
        for b in blocks:
            is_rack = b["name"] in Core.Layout06.RACK_BLOCKS
            snap_buf = 14 if is_rack else 8
            color = '#2980b9' if is_rack else '#34495e'
            lbl = f'{snap_buf}m road snap buffer'
            
            xs = [b["x"] - snap_buf, b["x"] + b["width"] + snap_buf,
                  b["x"] + b["width"] + snap_buf, b["x"] - snap_buf, b["x"] - snap_buf]
            ys = [b["y"] - snap_buf, b["y"] - snap_buf,
                  b["y"] + b["height"] + snap_buf, b["y"] + b["height"] + snap_buf, b["y"] - snap_buf]
            
            ax.plot(xs, ys, color=color, linestyle='--', linewidth=1.0,
                    alpha=0.8, zorder=1.8,
                    label=lbl if lbl not in legended_buffers else "")
            legended_buffers.add(lbl)

    # Rack-block per-side buffer rectangles (Step A) for the 5 "need rack" blocks.
    # 6 offsets total, split into two toggle groups:
    #   - "no rack" baseline (overlaps the default 8m+16m halos)
    #   - "with rack" (Case 1 / road 14m / Case 2 / b2b 28m)
    rack_buf = sketch.get("rack_buffers", {})
    if rack_buf:
        # (key, label, color, linestyle, linewidth, toggle_flag)
        rack_specs = [
            ("road_no_rack", '8m road (no-rack side)',     '#34495e', '--', 0.8, show_rack_no_rack),
            ("b2b_no_rack",  '16m b2b (no-rack side)',     '#c0392b', ':',  0.8, show_rack_no_rack),
            ("case1_rack",   'Case 1 rack CL (6m)',        '#00b894', '-',  1.6, show_rack_w_rack),
            ("road_w_rack",  '14m road (w-rack side)',     '#2980b9', '-',  1.2, show_rack_w_rack),
            ("case2_rack",   'Case 2 rack CL (22m)',       '#8e44ad', ':',  1.4, show_rack_w_rack),
            ("b2b_w_rack",   '28m b2b (w-rack side)',      '#e67e22', ':',  1.0, show_rack_w_rack),
        ]
        legended = {spec[0]: False for spec in rack_specs}
        for bname, offsets in rack_buf.items():
            for key, lbl, color, ls, lw, toggle in rack_specs:
                if not toggle or key not in offsets:
                    continue
                rx, ry, rw, rh = offsets[key]
                xs = [rx, rx + rw, rx + rw, rx, rx]
                ys = [ry, ry, ry + rh, ry + rh, ry]
                ax.plot(xs, ys, color=color, linestyle=ls, linewidth=lw,
                        alpha=0.9, zorder=2.5,
                        label=lbl if not legended[key] else "")
                legended[key] = True

    # Rack spines (B-1)
    rack_segments = sketch.get("rack_segments", [])
    for i, seg in enumerate(rack_segments):
        if seg and len(seg) == 2:
            xs, ys = zip(*seg)
            ax.plot(xs, ys, color='#d35400', linewidth=2, linestyle='-', zorder=3.5, 
                    label='PB-CT Spine (B-1)' if i==0 else "")
            
    # Candidate points (B-2, B-3)
    rack_candidates = sketch.get("rack_candidates", [])
    for i, pt in enumerate(rack_candidates):
        ax.plot(pt[0], pt[1], 'o', color='#bdc3c7', markersize=4, zorder=3.6, 
                label='RAW/Demi Candidates' if i==0 else "")

    # Water Triangle (B-4)
    water_triangle = sketch.get("water_triangle", [])
    for i, pt in enumerate(water_triangle):
        ax.plot(pt[0], pt[1], '*', color='#f1c40f', markersize=12, markeredgecolor='black', zorder=3.7, 
                label='WWT/RAW/Demi Final Points (B-4)' if i==0 else "")
    if len(water_triangle) == 3:
        # Draw lines connecting them
        wx, wy = zip(*(water_triangle + [water_triangle[0]]))
        ax.plot(wx, wy, color='#f1c40f', linestyle=':', linewidth=1, zorder=3.6)

    # Boom Barrier
    boom_barrier = sketch.get("boom_barrier", [])
    if boom_barrier and len(boom_barrier) == 2:
        xs, ys = zip(*boom_barrier)
        ax.plot(xs, ys, color='#e74c3c', linewidth=4, linestyle='-', zorder=4.0, label='Boom Barrier')

    # Gate Death Zone
    gate_death_zone = sketch.get("gate_death_zone")
    if gate_death_zone:
        gx, gy, gw, gh = gate_death_zone
        import matplotlib.patches as patches
        rect = patches.Rectangle((gx, gy), gw, gh, linewidth=1.5, edgecolor='#c0392b',
                                 facecolor='#e74c3c', alpha=0.2, hatch='///', zorder=1.1, label='Gate Death Zone')
        ax.add_patch(rect)


    # Blocks (circles for Tanks + Flare per Groups.SHAPES, rectangles otherwise)
    for b in blocks:
        x, y, w, h = b["x"], b["y"], b["width"], b["height"]
        if SHAPES.get(b["name"]) == "circle":
            r = min(w, h) / 2
            cx, cy = x + w / 2, y + h / 2
            ax.add_patch(mpatches.Circle((cx, cy), r, facecolor=b["color"], alpha=0.55, zorder=2))
            ax.add_patch(mpatches.Circle((cx, cy), r, fill=False, edgecolor=b["color"], lw=1.0, zorder=2.1))
        else:
            ax.fill([x,x+w,x+w,x,x], [y,y,y+h,y+h,y], color=b["color"], alpha=0.55, zorder=2)
            ax.plot([x,x+w,x+w,x,x], [y,y,y+h,y+h,y], color=b["color"], lw=1.0, zorder=2.1)
        ax.text(x + w/2, y + h/2, b["name"], color='white', fontsize=5.5,
                fontweight='bold', ha='center', va='center', zorder=3,
                bbox=dict(facecolor='#333', alpha=0.75, edgecolor='none', pad=1))

    # Gate marker
    gx, gy = gate_pt
    ax.plot(gx, gy, '^', color='#27ae60', markersize=14, zorder=6,
            markeredgecolor='white', markeredgewidth=1.0)
    ax.text(gx, gy + 8, 'GATE', color='#27ae60', fontsize=9,
            fontweight='bold', ha='center', va='bottom', zorder=6)

    ax.set_xlim(-20, sw + 20)
    ax.set_ylim(-20, sl + 20)
    ax.set_aspect('equal', adjustable='box')
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values(): sp.set_visible(False)
    if show_legend:
        ax.legend(loc='upper left', fontsize=8, framealpha=0.9)

    plt.tight_layout(pad=0.4)
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)

    # Stats
    st.divider()
    st.markdown("#### Block stats")
    rows = [{"Block": b["name"], "X (m)": b["x"], "Y (m)": b["y"],
             "W (m)": b["width"], "H (m)": b["height"]} for b in blocks]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Blocks placed", len(blocks))
    c2.metric("Grid cell size", f"{CELL_SIZE}m")
    c3.metric("Fire segs (kept)",  len(sketch.get("fire_segments", [])))
    c4.metric("Secondary segs",    len(sketch.get("secondary_segs", [])))
    c5.metric("Pruned segs",       len(sketch.get("pruned_segments", [])))

    # Per-block kept path table (Step 1.5 — shorter of ring/perimeter, Power Block excluded)
    traces = sketch.get("path_traces", [])
    if traces:
        st.markdown("#### Kept paths (Step 1.5 — shorter of ring/perimeter)")
        trace_rows = []
        for t in traces:
            pts = t["world"]
            length = sum(((pts[i][0]-pts[i-1][0])**2 + (pts[i][1]-pts[i-1][1])**2)**0.5
                         for i in range(1, len(pts)))
            trace_rows.append({
                "Block":  t["block"],
                "via":    t["via"],
                "length (m)": round(length, 1),
                "cells":  len(pts),
            })
        st.dataframe(trace_rows, use_container_width=True, hide_index=True)
    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 05 (unchanged below)
# ══════════════════════════════════════════════════════════════════════════════

st.sidebar.header("Generation")
boundary_margin = st.sidebar.slider("Boundary Margin", -50, 50, -20, step=5)
min_passing = st.sidebar.slider("Min rules passing", 1, len(RULES), 1)
fix_seed = st.sidebar.checkbox("Fix building positions (seed)", value=True)
seed_val = st.sidebar.number_input("Random seed", min_value=0, max_value=10_000,
                                   value=42, step=1, disabled=not fix_seed)

st.sidebar.divider()
st.sidebar.header("Overlays")
show_grid    = st.sidebar.checkbox("Grid lines",          value=False)
show_blocked = st.sidebar.checkbox("Blocked cells (3m buffer)", value=True)
show_paths   = st.sidebar.checkbox("A* path cells",       value=True)
show_smooth  = st.sidebar.checkbox("Smoothed road lines", value=True)
show_snaps   = st.sidebar.checkbox("Gate/entrance snap cells", value=True)
show_racks   = st.sidebar.checkbox("Racks",               value=True)
show_entrances = st.sidebar.checkbox("Entrance points",   value=True)

st.title("Road Logic Test Page")
st.caption(
    f"Site **{site_width}×{site_length} m** | Wind **{wind_dir}** | "
    f"Gate **{gate_side}@{gate_ratio:.2f}** | "
    f"GH **{gh_edge}@{gh_ratio:.2f}/{gh_offset}m** | "
    f"GIS **{gis_edge}@{gis_ratio:.2f}/{gis_offset}m** | "
    f"RAW Water **{water_edge}@{water_ratio:.2f}/{water_offset}m** | "
    f"Min rules **{min_passing}/{len(RULES)}**"
)

bldg_sig = (
    site_width, site_length, wind_dir,
    gate_side, gate_ratio,
    gh_edge, gh_ratio, gh_offset,
    gis_edge, gis_ratio, gis_offset,
    water_edge, water_ratio, water_offset,
    boundary_margin, min_passing,
    int(seed_val) if fix_seed else None,
)

btn_col1, btn_col2 = st.columns([3, 2])
with btn_col1:
    do_generate = st.button("Generate Layout", use_container_width=True, type="primary")
with btn_col2:
    do_reroll = st.button("Re-roll buildings", use_container_width=True)

if do_generate or do_reroll:
    cached_sig    = st.session_state.get("bldg_sig")
    cached_layout = st.session_state.get("layout")
    reuse_buildings = (
        do_generate and not do_reroll and fix_seed
        and cached_sig == bldg_sig and cached_layout is not None
    )

    if reuse_buildings:
        with st.spinner("Recomputing roads on cached buildings..."):
            layout = cached_layout
            new_road = build_road_network(
                site_width, site_length, layout["groups"], layout["gate_point"]
            )
            if new_road is not None:
                layout = {**layout, "road": new_road}
                st.session_state["layout"] = layout
            else:
                st.warning("Road network unreachable — try Re-roll.")
    else:
        if fix_seed and not do_reroll:
            random.seed(int(seed_val))
        with st.spinner("Generating one layout..."):
            results = generate_layouts(
                site_width, site_length, wind_dir,
                n_results=1, min_rules_passing=min_passing, max_pool=300,
                gate_side=gate_side, gate_ratio=gate_ratio,
                gh_edge=gh_edge, gh_ratio=gh_ratio, gh_offset=gh_offset,
                gis_edge=gis_edge, gis_ratio=gis_ratio, gis_offset=gis_offset,
                water_edge=water_edge, water_ratio=water_ratio, water_offset=water_offset,
                boundary_margin=boundary_margin,
            )
        layout_new = results[0] if results else None
        st.session_state["layout"]   = layout_new
        st.session_state["bldg_sig"] = bldg_sig if layout_new else None

    st.session_state["params"] = (site_width, site_length, wind_dir)

layout = st.session_state.get("layout")
sw, sl, wd = st.session_state.get("params", (site_width, site_length, wind_dir))

if layout is None:
    if do_generate:
        st.error("No layout found — try lowering Min rules passing or changing site dims.")
    else:
        st.info("Set parameters in the sidebar, then click **Generate Layout**.")
    st.stop()

road  = layout.get("road", {})
grid  = road.get("grid")
segs  = road.get("segments", [])
gate  = layout.get("gate_point")

fig, ax = plt.subplots(figsize=(12, 8), dpi=110)
ax.fill([0,sw,sw,0,0], [0,0,sl,sl,0], color='#f7fbff', zorder=0)
ax.plot([0,sw,sw,0,0], [0,0,sl,sl,0], color='black', lw=1.2, zorder=1)

if grid is not None and show_blocked:
    blocked_img = grid.blocked.T.astype(float)
    ax.imshow(blocked_img,
              extent=(0, grid.ncols*grid.cell_size, 0, grid.nrows*grid.cell_size),
              origin='lower',
              cmap=mcolors.ListedColormap([(0,0,0,0),(0.85,0.25,0.25,0.28)]),
              interpolation='nearest', zorder=0.3)

if grid is not None and show_grid:
    cs = grid.cell_size
    for i in range(grid.ncols + 1): ax.axvline(i*cs, color='#cccccc', lw=0.25, zorder=0.5)
    for j in range(grid.nrows + 1): ax.axhline(j*cs, color='#cccccc', lw=0.25, zorder=0.5)

if grid is not None and show_paths and segs:
    cmap = cm.get_cmap('tab10', max(len(segs), 1))
    cs = grid.cell_size
    wc = road.get("width_cells", 0)
    drawn_cells = set()
    for k, seg in enumerate(segs):
        color = cmap(k % 10)
        for (i, j) in seg.get("path_cells", []):
            for di in range(-wc, wc + 1):
                for dj in range(-wc, wc + 1):
                    cell = (i+di, j+dj)
                    if cell not in drawn_cells:
                        drawn_cells.add(cell)
                        ax.add_patch(plt.Rectangle(
                            (cell[0]*cs, cell[1]*cs), cs, cs,
                            facecolor=color, alpha=0.35, edgecolor='none', zorder=0.6))

if show_smooth and segs:
    cmap = cm.get_cmap('tab10', max(len(segs), 1))
    for k, seg in enumerate(segs):
        pw = seg.get("path_world", [])
        if len(pw) >= 2:
            color = cmap(k % 10)
            rx, ry = zip(*pw)
            ax.plot(rx, ry, color=color, lw=16, alpha=0.7, zorder=2.5,
                    solid_capstyle='round', label=f"→ {seg.get('to', '?')}")

if show_racks:
    for rack in layout["racks"]:
        draw_rack(ax, rack)

for g in layout["groups"]:
    draw_group(ax, g)

if show_entrances:
    for g in layout["groups"]:
        for ex, ey in g.get("entrance_points", []):
            ax.plot(ex, ey, 'o', color='red', markersize=5, zorder=5,
                    markeredgecolor='white', markeredgewidth=0.7)

if grid is not None and show_snaps and segs:
    cs = grid.cell_size
    gate_seg = next((s for s in segs if s.get("path_cells")), None)
    first_cell = gate_seg["path_cells"][0] if gate_seg else None
    if first_cell:
        gi, gj = first_cell
        ax.add_patch(plt.Rectangle((gi*cs, gj*cs), cs, cs,
                                   facecolor='none', edgecolor='#27ae60', lw=2.0, zorder=3.5))
    for seg in segs:
        cells = seg.get("path_cells", [])
        if cells:
            ei, ej = cells[-1]
            ax.add_patch(plt.Rectangle((ei*cs, ej*cs), cs, cs,
                                       facecolor='none', edgecolor='red', lw=1.5, zorder=3.5))

if gate:
    gx, gy = gate
    ax.plot(gx, gy, '^', color='#27ae60', markersize=14, zorder=6,
            markeredgecolor='white', markeredgewidth=1.0)
    ax.text(gx, gy+8, 'GATE', color='#27ae60', fontsize=9,
            fontweight='bold', ha='center', va='bottom', zorder=6)

ax.set_xlim(-20, sw+20); ax.set_ylim(-20, sl+20)
ax.set_aspect('equal', adjustable='box')
ax.set_xticks([]); ax.set_yticks([])
for sp in ax.spines.values(): sp.set_visible(False)
if show_smooth and segs:
    ax.legend(loc='upper left', fontsize=6, framealpha=0.85, ncol=2)
plt.tight_layout(pad=0.4)
st.pyplot(fig, use_container_width=True)
plt.close(fig)

st.divider()
st.markdown("#### Road network stats")
if grid is not None:
    free  = int((~grid.blocked).sum())
    total = grid.ncols * grid.nrows
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Grid size", f"{grid.ncols} × {grid.nrows}")
    c2.metric("Cell size", f"{grid.cell_size} m")
    c3.metric("Free cells", f"{free} / {total}")
    c4.metric("Segments", str(len(segs)))

if segs:
    rows = []
    for seg in segs:
        pw = seg.get("path_world", [])
        length_m = sum(
            ((pw[i][0]-pw[i-1][0])**2 + (pw[i][1]-pw[i-1][1])**2)**0.5
            for i in range(1, len(pw))
        )
        rows.append({"to": seg.get("to","?"), "cells": len(seg.get("path_cells",[])),
                     "length (m)": round(length_m, 1), "to_point": seg.get("to_point")})
    st.dataframe(rows, use_container_width=True, hide_index=True)

scoring = layout["scoring"]
passing = sum(1 for r in scoring["results"] if r["passed"])
st.caption(f"**Score:** {scoring['total_penalty']:,.0f} pts | "
           f"{passing}/{len(scoring['results'])} rules passing")

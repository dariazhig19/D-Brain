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
from Core.Layout06 import generate_sketch, CELL_SIZE

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
    st.caption("Steps 1.1–1.5: blocks · ring + perimeter fire roads · stubs · 2-path verification + pruning")

    st.sidebar.header("Phase 06 Settings")
    show_grid     = st.sidebar.checkbox("2m Grid lines", value=False)
    show_buffer   = st.sidebar.checkbox("Block 8m + 16m buffers", value=True)
    show_rack_buf = st.sidebar.checkbox("Rack buffers (Case 1 & 2)", value=True)
    show_raw      = st.sidebar.checkbox("Raw stubs (pre-prune)", value=False)
    show_pruned   = st.sidebar.checkbox("Pruned segments (red)", value=True)
    show_kept     = st.sidebar.checkbox("Kept graph (fire + secondary)", value=True)
    show_traces   = st.sidebar.checkbox("2-path traces (per block)", value=False)
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
    perimeter     = sketch["perimeter_road"]
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

    # Underlay: full ring + perimeter polyline (always shown, faintly)
    px, py = zip(*perimeter)
    ax.plot(px, py, color='#888888', lw=0.5, alpha=0.5, zorder=1.4,
            linestyle='--', solid_capstyle='round', label='Perimeter CL (raw)')
    rx, ry = zip(*ring_road)
    ax.plot(rx, ry, color='#888888', lw=0.5, alpha=0.5, zorder=1.5,
            linestyle='--', solid_capstyle='round', label='Ring CL (raw)')
    # Gate spur (perimeter → gate point) — short primary segment
    gs = sketch.get("gate_spur") or []
    if len(gs) >= 2:
        gsx, gsy = zip(*gs)
        ax.plot(gsx, gsy, color='#888888', lw=0.5, alpha=0.5, zorder=1.5,
                linestyle='--', solid_capstyle='round', label='Gate spur (raw)')
    # Ring spur (ring → perimeter) — primary connector around blocks
    rs = sketch.get("ring_spur") or []
    if len(rs) >= 2:
        rsx, rsy = zip(*rs)
        ax.plot(rsx, rsy, color='#888888', lw=0.5, alpha=0.5, zorder=1.5,
                linestyle='--', solid_capstyle='round', label='Ring spur (raw)')

    # Raw stubs (pre-prune) — show all stub paths regardless of pruning decision
    stubs = sketch.get("stubs", {})
    if show_raw:
        first_stub = True
        for bname, block_st in stubs.items():
            for key, color, label_suffix in [("ring_stub", "#1abc9c", "to Ring"), ("perimeter_stub", "#2980b9", "to Perimeter")]:
                path = block_st.get(key, [])
                if len(path) >= 2:
                    sx, sy = zip(*path)
                    ax.plot(sx, sy, color=color, lw=1.0, ls=':', alpha=0.6, zorder=1.7,
                            label=f'Raw stub ({label_suffix})' if first_stub else "")
            first_stub = False

    # Pruned segments (Step 1.5) — what got removed because no path used it
    if show_pruned:
        pruned_segs = sketch.get("pruned_segments", [])
        for k, ((x1, y1), (x2, y2)) in enumerate(pruned_segs):
            ax.plot([x1, x2], [y1, y2], color='#c0392b', lw=0.8, alpha=0.55, zorder=1.6,
                    label='Pruned segment' if k == 0 else "")

    # Kept graph (Step 1.5/1.6) — fire (primary, pink) + secondary (blue)
    if show_kept:
        fire_segs = sketch.get("fire_segments", [])
        for k, ((x1, y1), (x2, y2)) in enumerate(fire_segs):
            ax.plot([x1, x2], [y1, y2], color='#e91e8c', lw=2.0, alpha=0.95, zorder=2.5,
                    solid_capstyle='round',
                    label='Primary Fire Road (kept)' if k == 0 else "")
        sec_segs = sketch.get("secondary_segs", [])
        for k, ((x1, y1), (x2, y2)) in enumerate(sec_segs):
            ax.plot([x1, x2], [y1, y2], color='#2980b9', lw=1.6, alpha=0.9, zorder=2.4,
                    solid_capstyle='round',
                    label='Secondary Stub (kept)' if k == 0 else "")

    # 2-path traces (Step 1.5 verification) — overlay each block's two routes to gate
    if show_traces:
        traces = sketch.get("path_traces", [])
        trace_colors = {"ring": "#16a085", "perimeter": "#f39c12"}
        legended = {"ring": False, "perimeter": False}
        for tr in traces:
            via = tr["via"]
            pts = tr["world"]
            if len(pts) < 2:
                continue
            tx, ty = zip(*pts)
            lbl = f"Path via {via}" if not legended[via] else ""
            legended[via] = True
            ax.plot(tx, ty, color=trace_colors[via], lw=0.7, alpha=0.6, zorder=2.6,
                    label=lbl)

    # Two buffer halos per block:
    #  - 8m halo (inner, dashed): road buffer — no fire-road centerline inside
    #  - 16m halo (outer, dotted): block-to-block clearance — no other block edge inside
    if show_buffer:
        for k, b in enumerate(blocks):
            for buf, color, ls, lbl in (
                (8,  '#34495e', '--', '8m road buffer'),
                (16, '#c0392b', ':',  '16m block-to-block buffer'),
            ):
                xs = [b["x"] - buf, b["x"] + b["width"] + buf,
                      b["x"] + b["width"] + buf, b["x"] - buf, b["x"] - buf]
                ys = [b["y"] - buf, b["y"] - buf,
                      b["y"] + b["height"] + buf, b["y"] + b["height"] + buf, b["y"] - buf]
                ax.plot(xs, ys, color=color, linestyle=ls, linewidth=1.0,
                        alpha=0.8, zorder=1.8,
                        label=lbl if k == 0 else "")

    # Rack-buffer rectangles (Step A) for the 5 "need rack" blocks:
    #  - Case 1 (8m offset, teal dashed): rack between block and road
    #  - Case 2 (26m offset, purple dotted): road between block and rack
    if show_rack_buf:
        rack_buf = sketch.get("rack_buffers", {})
        legended = {"case1": False, "case2": False}
        for bname, cases in rack_buf.items():
            for case_key, color, ls, lbl in (
                ("case1", '#16a085', '--', 'Rack buffer Case 1 (8m)'),
                ("case2", '#8e44ad', ':',  'Rack buffer Case 2 (26m)'),
            ):
                rx, ry, rw, rh = cases[case_key]
                xs = [rx, rx + rw, rx + rw, rx, rx]
                ys = [ry, ry, ry + rh, ry + rh, ry]
                ax.plot(xs, ys, color=color, linestyle=ls, linewidth=1.0,
                        alpha=0.7, zorder=1.75,
                        label=lbl if not legended[case_key] else "")
                legended[case_key] = True

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

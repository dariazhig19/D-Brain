"""Single-layout road debugging dashboard.

Run with:
    streamlit run 01_Products/Layout_Gen_Design/Dashboard/Roads_Test.py

Generates ONE layout per button click and renders a large figure with
toggleable overlays so the A* road logic can be inspected cell-by-cell.
"""

import streamlit as st
import sys, os, random
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import matplotlib.pyplot as plt
from matplotlib import cm, colors as mcolors

import importlib
import Core.Groups, Core.Roads, Core.Rules, Core.Main, Core.Grid, Core.Pathfind
importlib.reload(Core.Grid)
importlib.reload(Core.Pathfind)
importlib.reload(Core.Groups)
importlib.reload(Core.Roads)
importlib.reload(Core.Rules)
importlib.reload(Core.Main)
from Core.Groups import draw_group, draw_rack
from Core.Rules import RULES
from Core.Main import generate_layouts

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

st.set_page_config(page_title="Roads Test", layout="wide")

# ── Sidebar: site + gate + GIS ─────────────────────────────────────────────
st.sidebar.header("Site")
site_width  = st.sidebar.slider("Plot Width (A)",  100, 1000, 500, step=10)
site_length = st.sidebar.slider("Plot Length (B)", 100, 1000, 270, step=10)
wind_dir    = st.sidebar.selectbox("Wind Direction",
                                   ["North", "South", "East", "West"], index=2)

st.sidebar.divider()
st.sidebar.header("Gate")
gate_side   = st.sidebar.selectbox("Gate edge", ["N", "S", "E", "W"], index=0)
gate_ratio  = st.sidebar.slider("Gate position along edge", 0.1, 0.9, 0.5, step=0.05)
gh_position = st.sidebar.selectbox("Gate House side", ["right", "left"], index=0)

st.sidebar.divider()
st.sidebar.header("Anchors")
gis_corner  = st.sidebar.selectbox("GIS corner", ["NE", "NW", "SE", "SW"], index=0)

st.sidebar.divider()
st.sidebar.header("Generation")
boundary_margin = st.sidebar.slider("Boundary Margin (offset)", -50, 50, -20, step=5,
                                    help="Minimum distance from buildings to the plot boundary. Negative values allow overlapping the boundary.")
min_passing = st.sidebar.slider("Min rules passing", 1, len(RULES), 1,
                                help="Keep low for road testing — high values may fail to find a layout.")
fix_seed = st.sidebar.checkbox("Fix building positions (seed)", value=True,
                               help="When ON, the same site + gate + GIS + seed produces the same buildings every click. "
                                    "Lets you iterate on road logic against a stable layout.")
seed_val = st.sidebar.number_input("Random seed", min_value=0, max_value=10_000, value=42, step=1,
                                   disabled=not fix_seed)

st.sidebar.divider()
st.sidebar.header("Overlays")
show_grid    = st.sidebar.checkbox("Grid lines",          value=False)
show_blocked = st.sidebar.checkbox("Blocked cells (3m buffer)", value=True)
show_paths   = st.sidebar.checkbox("A* path cells",       value=True)
show_smooth  = st.sidebar.checkbox("Smoothed road lines", value=True)
show_snaps   = st.sidebar.checkbox("Gate/entrance snap cells", value=True)
show_racks   = st.sidebar.checkbox("Racks",               value=True)
show_entrances = st.sidebar.checkbox("Entrance points",   value=True)

# ── Header ─────────────────────────────────────────────────────────────────
st.title("Road Logic Test Page")
st.caption(
    f"Site **{site_width}×{site_length} m** | Wind **{wind_dir}** | "
    f"Gate **{gate_side}@{gate_ratio:.2f}** | GIS **{gis_corner}** | "
    f"Min rules **{min_passing}/{len(RULES)}**"
)

_, btn_col, _ = st.columns([2, 3, 2])
with btn_col:
    do_generate = st.button("Generate Layout", use_container_width=True, type="primary")

if do_generate:
    if fix_seed:
        random.seed(int(seed_val))
    with st.spinner("Generating one layout..."):
        results = generate_layouts(
            site_width, site_length, wind_dir,
            n_results=1,
            min_rules_passing=min_passing,
            gate_side=gate_side,
            gate_ratio=gate_ratio,
            gh_position=gh_position,
            gis_corner=gis_corner,
            boundary_margin=boundary_margin,
        )
    st.session_state["layout"] = results[0] if results else None
    st.session_state["params"] = (site_width, site_length, wind_dir)

layout = st.session_state.get("layout")
sw, sl, wd = st.session_state.get("params", (site_width, site_length, wind_dir))

if layout is None:
    if do_generate:
        st.error("No layout found — try lowering Min rules passing or changing site dims.")
    else:
        st.info("Set parameters in the sidebar, then click **Generate Layout**.")
    st.stop()

# ── Render the layout ──────────────────────────────────────────────────────
road  = layout.get("road", {})
grid  = road.get("grid")
segs  = road.get("segments", [])
gate  = layout.get("gate_point")

fig, ax = plt.subplots(figsize=(12, 8), dpi=110)

# Site boundary
ax.fill([0, sw, sw, 0, 0], [0, 0, sl, sl, 0], color='#f7fbff', zorder=0)
ax.plot([0, sw, sw, 0, 0], [0, 0, sl, sl, 0], color='black', lw=1.2, zorder=1)

# Blocked cells overlay (the 3m inflated buffer A* sees as walls)
if grid is not None and show_blocked:
    blocked_img = grid.blocked.T.astype(float)
    ax.imshow(
        blocked_img,
        extent=(0, grid.ncols * grid.cell_size,
                0, grid.nrows * grid.cell_size),
        origin='lower',
        cmap=mcolors.ListedColormap([(0, 0, 0, 0), (0.85, 0.25, 0.25, 0.28)]),
        interpolation='nearest',
        zorder=0.3,
    )

# Grid lines
if grid is not None and show_grid:
    cs = grid.cell_size
    for i in range(grid.ncols + 1):
        ax.axvline(i * cs, color='#cccccc', lw=0.25, zorder=0.5)
    for j in range(grid.nrows + 1):
        ax.axhline(j * cs, color='#cccccc', lw=0.25, zorder=0.5)

# A* path cells (raw cell-level waypoints, color-coded per destination)
if grid is not None and show_paths and segs:
    cmap = cm.get_cmap('tab10', max(len(segs), 1))
    cs = grid.cell_size
    for k, seg in enumerate(segs):
        color = cmap(k % 10)
        for (i, j) in seg.get("path_cells", []):
            ax.add_patch(plt.Rectangle(
                (i * cs, j * cs), cs, cs,
                facecolor=color, alpha=0.35, edgecolor='none', zorder=0.6,
            ))

# Smoothed road lines (cell-center polyline)
if show_smooth and segs:
    cmap = cm.get_cmap('tab10', max(len(segs), 1))
    for k, seg in enumerate(segs):
        pw = seg.get("path_world", [])
        if len(pw) >= 2:
            color = cmap(k % 10)
            rx, ry = zip(*pw)
            ax.plot(rx, ry, color=color, lw=2.2, zorder=2.5,
                    solid_capstyle='round',
                    label=f"→ {seg.get('to', '?')}")

# Racks
if show_racks:
    for rack in layout["racks"]:
        draw_rack(ax, rack)

# Buildings (draw_group already renders the name label in the centre)
for g in layout["groups"]:
    draw_group(ax, g)

# Entrance points (red dots) + snap cells
if show_entrances:
    for g in layout["groups"]:
        for ex, ey in g.get("entrance_points", []):
            ax.plot(ex, ey, 'o', color='red', markersize=5, zorder=5,
                    markeredgecolor='white', markeredgewidth=0.7)

# Snap cells — where gate / entrance got moved to by snap_to_passable
if grid is not None and show_snaps and segs:
    cs = grid.cell_size
    # Gate snap = first cell of the first segment
    first_cell = segs[0].get("path_cells", [None])[0] if segs else None
    if first_cell is not None:
        gi, gj = first_cell
        ax.add_patch(plt.Rectangle(
            (gi * cs, gj * cs), cs, cs,
            facecolor='none', edgecolor='#27ae60', lw=2.0, zorder=3.5,
        ))
    # Entrance snaps = last cell of each segment
    for seg in segs:
        cells = seg.get("path_cells", [])
        if cells:
            ei, ej = cells[-1]
            ax.add_patch(plt.Rectangle(
                (ei * cs, ej * cs), cs, cs,
                facecolor='none', edgecolor='red', lw=1.5, zorder=3.5,
            ))

# Gate marker
if gate:
    gx, gy = gate
    ax.plot(gx, gy, '^', color='#27ae60', markersize=14, zorder=6,
            markeredgecolor='white', markeredgewidth=1.0)
    ax.text(gx, gy + 8, 'GATE', color='#27ae60', fontsize=9,
            fontweight='bold', ha='center', va='bottom', zorder=6)

ax.set_xlim(-20, sw + 20)
ax.set_ylim(-20, sl + 20)
ax.set_aspect('equal', adjustable='box')
ax.set_xticks([])
ax.set_yticks([])
for sp in ax.spines.values():
    sp.set_visible(False)

if show_smooth and segs:
    ax.legend(loc='upper left', fontsize=6, framealpha=0.85, ncol=2)

plt.tight_layout(pad=0.4)
st.pyplot(fig, use_container_width=True)
plt.close(fig)

# ── Road stats ─────────────────────────────────────────────────────────────
st.divider()
st.markdown("#### Road network stats")

if grid is not None:
    free = int((~grid.blocked).sum())
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
        length_m = 0.0
        for i in range(1, len(pw)):
            length_m += ((pw[i][0]-pw[i-1][0])**2 + (pw[i][1]-pw[i-1][1])**2) ** 0.5
        rows.append({
            "to":          seg.get("to", "?"),
            "cells":       len(seg.get("path_cells", [])),
            "length (m)":  round(length_m, 1),
            "to_point":    seg.get("to_point"),
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)

# ── Score summary ──────────────────────────────────────────────────────────
scoring = layout["scoring"]
passing = sum(1 for r in scoring["results"] if r["passed"])
st.caption(f"**Score:** {scoring['total_penalty']:,.0f} pts | "
           f"{passing}/{len(scoring['results'])} rules passing")

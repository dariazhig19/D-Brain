import streamlit as st
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import matplotlib.pyplot as plt
import io, base64, math

import importlib
import Core.Groups, Core.Roads, Core.Rules, Core.Main, Core.Exporter
importlib.reload(Core.Groups)
importlib.reload(Core.Roads)
importlib.reload(Core.Rules)
importlib.reload(Core.Main)
importlib.reload(Core.Exporter)
from Core.Groups import get_all_groups, get_all_racks, draw_group, draw_rack, FOOTPRINTS, compute_gate_point
from Core.Rules import RULES
from Core.Main import generate_layouts
from Core.Exporter import export_to_dxf

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

# ── Page config ────────────────────────────────────────────────────────────
st.set_page_config(page_title="PowerPlan AI", layout="wide")

st.markdown("""
<style>
[data-testid="stPyplot"] > div { display:flex; justify-content:center; }
div[data-testid="stHorizontalBlock"] > div { padding: 4px; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ────────────────────────────────────────────────────────────────
st.sidebar.header("Site Information")
site_width  = st.sidebar.slider("Plot Width (A)",  100, 1000, 500, step=10)
site_length = st.sidebar.slider("Plot Length (B)", 100, 1000, 270, step=10)
wind_dir    = st.sidebar.selectbox("Wind Direction",
                                   ["North", "South", "East", "West"], index=2)
st.sidebar.divider()
st.sidebar.header("Site Gate")
gate_side = st.sidebar.selectbox("Gate edge",
                                  ["N", "S", "E", "W"], index=0,
                                  help="Which site boundary edge the gate (plot entrance) is on.")
gate_ratio = st.sidebar.slider("Gate position along edge", 0.1, 0.9, 0.5, step=0.05,
                                help="0.0 = left/bottom end, 0.5 = center, 1.0 = right/top end.")
st.sidebar.divider()
st.sidebar.header("Fixed Anchors")

st.sidebar.subheader("Gate House Anchor")
gh_edge = st.sidebar.selectbox("Edge (GH)", ["N", "S", "E", "W"], index=0)
gh_ratio = st.sidebar.slider("Position (GH)", 0.0, 1.0, 0.5, step=0.05)
gh_offset = st.sidebar.slider("Offset (GH)", 0, 50, 0, step=1)

st.sidebar.subheader("GIS Anchor")
gis_edge = st.sidebar.selectbox("Edge (GIS)", ["N", "S", "E", "W"], index=1)
gis_ratio = st.sidebar.slider("Position (GIS)", 0.0, 1.0, 0.8, step=0.05)
gis_offset = st.sidebar.slider("Offset (GIS)", 0, 50, 0, step=1)

st.sidebar.subheader("Water Anchor")
water_edge = st.sidebar.selectbox("Edge (Water)", ["N", "S", "E", "W"], index=2)
water_ratio = st.sidebar.slider("Position (Water)", 0.0, 1.0, 0.2, step=0.05)
water_offset = st.sidebar.slider("Offset (Water)", 0, 50, 0, step=1)
st.sidebar.divider()
st.sidebar.header("Generation Settings")
boundary_margin = st.sidebar.slider("Boundary Margin (offset)", -50, 50, -20, step=5,
                                    help="Minimum distance from buildings to the plot boundary. Negative values allow overlapping the boundary.")
n_results   = st.sidebar.slider("Layouts to generate", 5, 100, 10, step=5)
min_passing = st.sidebar.slider("Min rules passing",    1,  len(RULES),  12)

# ── Header ─────────────────────────────────────────────────────────────────
st.title("PowerPlan AI: Layout Generator")
st.markdown("### Phase_05: Infrastructure-First Layout Engine")
st.caption(
    f"Site: **{site_width} x {site_length} m** | Wind: **{wind_dir}** | "
    f"Target: **{n_results} layouts** with **>= {min_passing} / {len(RULES)} rules** passing"
)

# ── Generate button ────────────────────────────────────────────────────────
_, btn_col, _ = st.columns([2, 3, 2])
with btn_col:
    do_generate = st.button("Generate Layouts", use_container_width=True, type="primary")

if do_generate:
    with st.spinner(f"Running constrained placement engine..."):
        results = generate_layouts(
            site_width, site_length, wind_dir,
            n_results=n_results,
            min_rules_passing=min_passing,
            gate_side=gate_side,
            gate_ratio=gate_ratio,
            gh_edge=gh_edge,
            gh_ratio=gh_ratio,
            gh_offset=gh_offset,
            gis_edge=gis_edge,
            gis_ratio=gis_ratio,
            gis_offset=gis_offset,
            water_edge=water_edge,
            water_ratio=water_ratio,
            water_offset=water_offset,
            boundary_margin=boundary_margin,
        )
    st.session_state["results"] = results
    st.session_state["params"]  = (site_width, site_length, wind_dir)

# ── Render helpers ─────────────────────────────────────────────────────────
def _offset_loop(pts, dist):
    """Offset a closed polyline outward by ``dist`` metres using vertex normals.

    Returns (outer_pts, inner_pts). Assumes counter-clockwise traversal — the
    A* perimeter loop is generated CCW by ``_ring_waypoints``. Naive offsetting
    without miter handling; fine for the gently-curving roads A* produces, but
    can self-intersect on sharp corners.
    """
    n = len(pts)
    outer, inner = [], []
    for i in range(n):
        prev_x, prev_y = pts[(i - 1) % n]
        x, y           = pts[i]
        next_x, next_y = pts[(i + 1) % n]
        e1x, e1y = x - prev_x, y - prev_y
        e2x, e2y = next_x - x, next_y - y
        # Rotate each edge vector 90° CW to get the outward normal under CCW
        # traversal (pointing away from the loop interior).
        n1x, n1y =  e1y, -e1x
        n2x, n2y =  e2y, -e2x
        l1 = math.hypot(n1x, n1y) + 1e-9
        l2 = math.hypot(n2x, n2y) + 1e-9
        nx = n1x / l1 + n2x / l2
        ny = n1y / l1 + n2y / l2
        nl = math.hypot(nx, ny) + 1e-9
        nx, ny = nx / nl, ny / nl
        outer.append((x + dist * nx, y + dist * ny))
        inner.append((x - dist * nx, y - dist * ny))
    outer.append(outer[0])
    inner.append(inner[0])
    return outer, inner


def _fig_to_b64(fig, dpi=100):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=dpi)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode()
    plt.close(fig)
    return b64


def _render_layout(layout, sw, sl, wd, rank):
    """Build a compact thumbnail matplotlib figure for one layout."""
    fig, ax = plt.subplots(figsize=(4.5, 3.5), dpi=90)

    # Site boundary
    ax.fill([0, sw, sw, 0, 0], [0, 0, sl, sl, 0], color='#f0f8ff', zorder=0)
    ax.plot([0, sw, sw, 0, 0], [0, 0, sl, sl, 0], color='black', lw=1.0)

    # Internal road network — draw each A* path from gate to entrance
    road = layout.get("road", {})
    if road.get("mode") == "internal" and road.get("segments"):
        for seg in road["segments"]:
            pw = seg.get("path_world", [])
            if len(pw) >= 2:
                rx, ry = zip(*pw)
                ax.plot(rx, ry, color='#999999', lw=1.5, zorder=0.7, solid_capstyle='round')

    # Wind indicator
    wind_map = {
        "East":  ("<- E", sw+8,    sl/2),
        "West":  ("-> W", -8,      sl/2),
        "North": ("v N",  sw/2,    sl+8),
        "South": ("^ S",  sw/2,    -8),
    }
    wt, wx, wy = wind_map[wd]
    ax.text(wx, wy, wt, color='#0078D7', fontsize=6.5,
            fontweight='bold', ha='center', va='center')

    # Draw racks first (behind buildings)
    for rack in layout["racks"]:
        draw_rack(ax, rack)

    # Draw all buildings
    for g in layout["groups"]:
        draw_group(ax, g)

    # Draw entrance markers (red dots)
    for g in layout["groups"]:
        for ex, ey in g.get("entrance_points", []):
            ax.plot(ex, ey, 'o', color='red', markersize=3, zorder=5)

    # Draw site gate marker (green triangle on boundary)
    gate_pt = layout.get("gate_point")
    if gate_pt:
        gx, gy = gate_pt
        ax.plot(gx, gy, '^', color='#27ae60', markersize=7, zorder=6,
                markeredgecolor='white', markeredgewidth=0.5)
        ax.text(gx, gy + 6, 'GATE', color='#27ae60', fontsize=5,
                fontweight='bold', ha='center', va='bottom', zorder=6)

    # Violation overlays
    viols = layout["scoring"]["violations_by_group"]
    for g in layout["groups"]:
        if viols.get(g["name"]):
            x, y, w, h = g["x"], g["y"], g["width"], g["height"]
            ax.plot([x, x+w, x+w, x, x], [y, y, y+h, y+h, y],
                    color='crimson', lw=0.8, linestyle='--', zorder=4)
    # Rack violations
    for rack in layout["racks"]:
        if viols.get(rack["name"]):
            for p1, p2 in rack["segments"]:
                x1, y1 = p1
                x2, y2 = p2
                ax.plot([x1, x2], [y1, y2],
                        color='crimson', lw=1.0, linestyle='-', zorder=4, alpha=0.7)

    # Title
    total   = layout["scoring"]["total_penalty"]
    n_rules = len(layout["scoring"]["results"])
    passing = sum(1 for r in layout["scoring"]["results"] if r["passed"])
    medal   = "[BEST] " if rank == 1 else ""
    title_color = '#c0392b' if total > 0 else '#27ae60'
    ax.set_title(f"{medal}#{rank}  |  {total:,.0f} pts  |  {passing}/{n_rules} rules",
                 fontsize=7.5, fontweight='bold', color=title_color, pad=4)

    ax.set_xlim(-18, sw + 18)
    ax.set_ylim(-18, sl + 18)
    ax.set_aspect('equal', adjustable='box')
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)
    plt.tight_layout(pad=0.4)
    return fig


# ── Display results ────────────────────────────────────────────────────────
results  = st.session_state.get("results", [])
sw, sl, wd = st.session_state.get("params", (site_width, site_length, wind_dir))

if not results:
    st.info("Configure site parameters in the sidebar, then click **Generate Layouts**.")
else:
    st.divider()
    best  = results[0]["scoring"]["total_penalty"]
    worst = results[-1]["scoring"]["total_penalty"]
    n_rules = len(RULES)
    c1, c2, c3 = st.columns(3)
    c1.metric("Best Score",   f"{best:,.0f} pts")
    c2.metric("Worst Score",  f"{worst:,.0f} pts")
    c3.metric("Layouts Found", str(len(results)))

    st.markdown(f"#### All {len(results)} Layouts (sorted best to worst)")

    NUM_COLS = 4
    for row_start in range(0, len(results), NUM_COLS):
        row_results = results[row_start: row_start + NUM_COLS]
        cols = st.columns(NUM_COLS)
        for j, layout in enumerate(row_results):
            rank = row_start + j + 1
            with cols[j]:
                fig   = _render_layout(layout, sw, sl, wd, rank)
                b64   = _fig_to_b64(fig)
                st.markdown(
                    f'<img src="data:image/png;base64,{b64}" style="width:100%; border-radius:6px;"/>',
                    unsafe_allow_html=True,
                )
                passing = sum(1 for r in layout["scoring"]["results"] if r["passed"])
                total   = layout["scoring"]["total_penalty"]
                st.caption(f"**{total:,.0f} pts** | {passing}/{n_rules}")

    # ── Detailed expander for selected layout ─────────────────────────────
    st.divider()
    st.markdown("#### Detailed Rule Breakdown")
    selected = st.selectbox("Select layout to inspect",
                            options=list(range(1, len(results)+1)),
                            format_func=lambda i: f"Layout #{i} -- {results[i-1]['scoring']['total_penalty']:,.0f} pts")
    layout = results[selected - 1]
    scoring = layout["scoring"]

    col_s, col_p, col_f = st.columns(3)
    passing = sum(1 for r in scoring["results"] if r["passed"])
    failing = len(scoring["results"]) - passing
    col_s.metric("Total Penalty", f"{scoring['total_penalty']:,.0f} pts")
    col_p.metric("Passing", f"{passing} / {len(scoring['results'])}")
    col_f.metric("Failing", str(failing))

    for r in scoring["results"]:
        status_icon = "PASS" if r["passed"] else "FAIL"
        penalty_str = f"{r['penalty']:,.0f} pts"
        label = f"{status_icon} **{r['id']}** -- {r['name']}  |  Penalty: **{penalty_str}**"
        with st.expander(label, expanded=not r["passed"]):
            col_m, col_t, col_c = st.columns(3)
            col_m.markdown(f"**Measured**\n\n{r['measured']}")
            col_t.markdown(f"**Threshold**\n\n{r['threshold']}")
            col_c.markdown(f"**Calculation**\n\n{r['calc']}")

    # ── DXF Export ─────────────────────────────────────────────────────────
    st.divider()
    st.markdown("#### Export to CAD")
    st.caption(
        "Exports the selected layout as a **DXF file** (opens directly in AutoCAD, BricsCAD, Revit, etc.). "
        "All geometry is on separate named layers."
    )
    _, export_col, _ = st.columns([2, 3, 2])
    with export_col:
        try:
            dxf_stream = export_to_dxf(layout, sw, sl)
            filename   = f"PowerPlan_Layout_{selected:02d}_{int(scoring['total_penalty'])}pts.dxf"
            st.download_button(
                label="Download DXF",
                data=dxf_stream,
                file_name=filename,
                mime="application/dxf",
                use_container_width=True,
                type="primary",
            )
        except Exception as e:
            st.error(f"DXF export failed: {e}")

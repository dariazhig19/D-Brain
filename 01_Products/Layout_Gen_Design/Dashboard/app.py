import streamlit as st
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import matplotlib.pyplot as plt
import io, base64, math

import importlib
import Core.Groups, Core.Rules, Core.Main, Core.Exporter
importlib.reload(Core.Groups)
importlib.reload(Core.Rules)
importlib.reload(Core.Main)
importlib.reload(Core.Exporter)
from Core.Groups import get_groups, draw_group
from Core.Rules import evaluate_all
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
site_width  = st.sidebar.slider("Plot Width (A)",  100, 1000, 400, step=10)
site_length = st.sidebar.slider("Plot Length (B)", 100, 1000, 300, step=10)
wind_dir    = st.sidebar.selectbox("Wind Direction",
                                   ["North", "South", "East", "West"], index=2)
st.sidebar.divider()
st.sidebar.header("Generation Settings")
n_results   = st.sidebar.slider("Layouts to generate", 5, 20, 10, step=5)
min_passing = st.sidebar.slider("Min rules passing",    1,  6,  3)

# ── Header ─────────────────────────────────────────────────────────────────
st.title("⚡ PowerPlan AI: Layout Generator")
st.markdown("### Phase_03: Generative Layout Engine")
st.caption(
    f"Site: **{site_width} × {site_length} m** | Wind: **{wind_dir}** | "
    f"Target: **{n_results} layouts** with **≥ {min_passing} / 6 rules** passing"
)

# ── Generate button ────────────────────────────────────────────────────────
_, btn_col, _ = st.columns([2, 3, 2])
with btn_col:
    do_generate = st.button("🎲 Generate Layouts", use_container_width=True, type="primary")

if do_generate:
    with st.spinner(f"Running constrained placement engine — up to {n_results} results…"):
        results = generate_layouts(
            site_width, site_length, wind_dir,
            n_results=n_results,
            min_rules_passing=min_passing,
        )
    st.session_state["results"] = results
    st.session_state["params"]  = (site_width, site_length, wind_dir)

# ── Render helpers ─────────────────────────────────────────────────────────
def _fig_to_b64(fig, dpi=100):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=dpi)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode()
    plt.close(fig)
    return b64


def _render_layout(layout, sw, sl, wd, rank):
    """Build a compact thumbnail matplotlib figure for one layout."""
    fig, ax = plt.subplots(figsize=(4, 3.2), dpi=90)

    # Site boundary
    ax.fill([0, sw, sw, 0, 0], [0, 0, sl, sl, 0], color='#f0f8ff', zorder=0)
    ax.plot([0, sw, sw, 0, 0], [0, 0, sl, sl, 0], color='black', lw=1.0)

    # Road setback
    s = 5
    if sw > 2*s and sl > 2*s:
        ax.plot([s, sw-s, sw-s, s, s], [s, s, sl-s, sl-s, s],
                color='red', linestyle='--', lw=0.6)

    # Gate House (bottom-center)
    GH_W, GH_H = 12, 8
    gx = sw/2 - GH_W/2
    ax.fill([gx, gx+GH_W, gx+GH_W, gx, gx], [-GH_H, -GH_H, 0, 0, -GH_H],
            color='#5c4a32', alpha=0.85, zorder=2)
    ax.text(sw/2, -GH_H - 1, "Gate", ha='center', va='top',
            fontsize=5.5, color='#3a2e1e', fontweight='bold')

    # Wind indicator
    wind_map = {
        "East":  ("← E", sw+8,    sl/2),
        "West":  ("→ W", -8,      sl/2),
        "North": ("↓ N", sw/2,    sl+8),
        "South": ("↑ S", sw/2,    -8),
    }
    wt, wx, wy = wind_map[wd]
    ax.text(wx, wy, wt, color='#0078D7', fontsize=6.5,
            fontweight='bold', ha='center', va='center')

    # Buildings
    for g in layout["groups"]:
        draw_group(ax, g)

    # Violation overlays
    viols = layout["scoring"]["violations_by_group"]
    for g in layout["groups"]:
        if viols.get(g["name"]):
            x, y, w, h = g["x"], g["y"], g["width"], g["height"]
            ax.plot([x, x+w, x+w, x, x], [y, y, y+h, y+h, y],
                    color='crimson', lw=2.0, linestyle='--', zorder=4)

    # Inter-building distance lines
    def gcx(g): return g["x"] + g["width"]/2
    def gcy(g): return g["y"] + g["height"]/2
    grp = {g["name"]: g for g in layout["groups"]}
    pb, ct, adm = grp["Power Block"], grp["Cooling Tower"], grp["Admin Building"]
    d_ct_adm = math.dist((gcx(ct), gcy(ct)), (gcx(adm), gcy(adm)))
    col_ct_adm = 'crimson' if d_ct_adm < 50 else '#27ae60'

    for (g1, g2, col) in [(pb, ct, '#aaaaaa'), (pb, adm, '#aaaaaa'), (ct, adm, col_ct_adm)]:
        x1, y1, x2, y2 = gcx(g1), gcy(g1), gcx(g2), gcy(g2)
        dm = math.dist((x1, y1), (x2, y2))
        ax.plot([x1, x2], [y1, y2], '--', color=col, lw=0.7, alpha=0.7, zorder=3)
        ax.text((x1+x2)/2, (y1+y2)/2, f"{dm:.0f}m",
                ha='center', va='center', fontsize=5.0, color=col, fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.15', fc='white', ec=col, alpha=0.85, lw=0.5),
                zorder=6)

    # Title
    total   = layout["scoring"]["total_penalty"]
    passing = sum(1 for r in layout["scoring"]["results"] if r["passed"])
    medal   = "🏆 " if rank == 1 else ""
    title_color = '#c0392b' if total > 0 else '#27ae60'
    ax.set_title(f"{medal}#{rank}  |  {total:,.0f} pts  |  {passing}/6 rules ✓",
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
    st.info("👆 Configure site parameters in the sidebar, then click **Generate Layouts**.")
else:
    st.divider()
    best  = results[0]["scoring"]["total_penalty"]
    worst = results[-1]["scoring"]["total_penalty"]
    c1, c2, c3 = st.columns(3)
    c1.metric("🏆 Best Score",   f"{best:,.0f} pts")
    c2.metric("📊 Worst Score",  f"{worst:,.0f} pts")
    c3.metric("✅ Layouts Found", str(len(results)))

    st.markdown(f"#### All {len(results)} Layouts — sorted best → worst")

    NUM_COLS = 5
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
                # Rule breakdown per layout
                passing = sum(1 for r in layout["scoring"]["results"] if r["passed"])
                total   = layout["scoring"]["total_penalty"]
                st.caption(f"**{total:,.0f} pts** | {passing}/6 ✓")

    # ── Detailed expander for selected layout ─────────────────────────────
    st.divider()
    st.markdown("#### 🔍 Detailed Rule Breakdown")
    selected = st.selectbox("Select layout to inspect",
                            options=list(range(1, len(results)+1)),
                            format_func=lambda i: f"Layout #{i} — {results[i-1]['scoring']['total_penalty']:,.0f} pts")
    layout = results[selected - 1]
    scoring = layout["scoring"]

    col_s, col_p, col_f = st.columns(3)
    passing = sum(1 for r in scoring["results"] if r["passed"])
    failing = len(scoring["results"]) - passing
    col_s.metric("🏆 Total Penalty", f"{scoring['total_penalty']:,.0f} pts")
    col_p.metric("✅ Passing", f"{passing} / {len(scoring['results'])}")
    col_f.metric("❌ Failing", str(failing))

    for r in scoring["results"]:
        status_icon = "✅" if r["passed"] else "❌"
        penalty_str = f"{r['penalty']:,.0f} pts"
        label = f"{status_icon} **{r['id']}** — {r['name']}  |  Penalty: **{penalty_str}**"
        with st.expander(label, expanded=not r["passed"]):
            col_m, col_t, col_c = st.columns(3)
            col_m.markdown(f"**📐 Measured**\n\n{r['measured']}")
            col_t.markdown(f"**🎯 Threshold**\n\n{r['threshold']}")
            col_c.markdown(f"**🧮 Calculation**\n\n{r['calc']}")

    # ── DXF Export ─────────────────────────────────────────────────────────
    st.divider()
    st.markdown("#### 📐 Export to CAD")
    st.caption(
        "Exports the selected layout as a **DXF file** (opens directly in AutoCAD, BricsCAD, Revit, etc.). "
        "All geometry is on separate named layers. Save as DWG from AutoCAD if needed."
    )
    _, export_col, _ = st.columns([2, 3, 2])
    with export_col:
        try:
            dxf_stream = export_to_dxf(layout, sw, sl)
            filename   = f"PowerPlan_Layout_{selected:02d}_{int(scoring['total_penalty'])}pts.dxf"
            st.download_button(
                label="⬇️ Download DXF",
                data=dxf_stream,
                file_name=filename,
                mime="application/dxf",
                use_container_width=True,
                type="primary",
            )
        except Exception as e:
            st.error(f"DXF export failed: {e}")


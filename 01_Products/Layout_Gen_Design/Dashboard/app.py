import streamlit as st
import matplotlib.pyplot as plt
import io, base64
from Core.Groups import get_groups, draw_group

# Font: Malgun Gothic (pre-installed on Windows)
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False  # Fix minus sign rendering


# Page configuration
st.set_page_config(page_title="PowerPlan AI", layout="wide")

st.title("⚡ PowerPlan AI: Layout Generator")
st.markdown("### Phase_01: Site Boundary & Primary Road Setback")

# Center all st.pyplot figures inside their containers
st.markdown("""
<style>
[data-testid="stPyplot"] > div {
    display: flex;
    justify-content: center;
}
</style>
""", unsafe_allow_html=True)

# --- UI CONTROLS (Sliders on the left) ---
st.sidebar.header("Site Dimensions (m)")
site_width  = st.sidebar.slider("Plot Width (A)",  100, 1000, 400, step=10)
site_length = st.sidebar.slider("Plot Length (B)", 100, 1000, 300, step=10)

st.sidebar.divider()
st.sidebar.header("Manual Group Offsets (m)")

st.sidebar.subheader("Power Block")
pb_dx = st.sidebar.slider("PB X Offset", -200, 200, 0, step=5)
pb_dy = st.sidebar.slider("PB Y Offset", -200, 200, 0, step=5)

st.sidebar.subheader("Cooling Tower")
ct_dx = st.sidebar.slider("CT X Offset", -200, 200, 0, step=5)
ct_dy = st.sidebar.slider("CT Y Offset", -200, 200, 0, step=5)

st.sidebar.subheader("Admin Building")
adm_dx = st.sidebar.slider("Admin X Offset", -200, 200, 0, step=5)
adm_dy = st.sidebar.slider("Admin Y Offset", -200, 200, 0, step=5)

# --- CORE ENGINE (Matplotlib image) ---
# Fixed pixel size: figsize × dpi = exact pixels on screen
# (8, 6) × 100 dpi = 800 × 600 px — never changes with browser scale
FIG_W_PX, FIG_H_PX = 500, 300
DPI = 100
fig, ax = plt.subplots(figsize=(FIG_W_PX / DPI, FIG_H_PX / DPI), dpi=DPI)

# 1. Site boundary — explicit X,Y coordinate lines (future-ready for line export)
site_x = [0, site_width, site_width, 0,          0]
site_y = [0, 0,          site_length, site_length, 0]
ax.fill(site_x, site_y, color='#f0f8ff', zorder=0)          # light fill
ax.plot(site_x, site_y, color='black', linewidth=1.2,
        label='Site Boundary')                               # boundary line

# 2. Road setback — explicit X,Y coordinate lines (5m inward from all edges)
setback = 5
if site_width > 2 * setback and site_length > 2 * setback:
    s = setback
    sb_x = [s,           site_width-s, site_width-s, s,           s]
    sb_y = [s,           s,            site_length-s, site_length-s, s]
    ax.plot(sb_x, sb_y, color='red', linestyle='--', linewidth=0.8,
            label='Primary Road Setback (5m)')               # setback line

# 3. Main Building Groups
groups = get_groups(
    site_width, site_length,
    pb_dx=pb_dx, pb_dy=pb_dy,
    ct_dx=ct_dx, ct_dy=ct_dy,
    adm_dx=adm_dx, adm_dy=adm_dy
)
for g in groups:
    draw_group(ax, g)

# --- Plot view configuration ---
ax.set_xlim(-10, site_width + 10)
ax.set_ylim(-10, site_length + 10)
ax.set_aspect('equal', adjustable='box')  # equal scale, box shrinks to fit

# Hide axis tick numbers (no x/y values shown)
ax.set_xticks([])
ax.set_yticks([])

# Remove the matplotlib axes spine (the extra black frame around the plot)
for spine in ax.spines.values():
    spine.set_visible(False)

# Legend placed outside below the plot
ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.04),
          ncol=2, frameon=True, fontsize=8)
plt.tight_layout()

# --- DISPLAY CONFIG ---
NUM_COLS = 4       # ← change this freely: number of columns for multi-plot grid

# Collect all plots — add more figs here as new phases are built
plots = [fig, fig, fig, fig]       # Phase 1: Site Boundary


def render_centered(container, plot_fig, width_px):
    """Render a matplotlib figure centered inside a Streamlit container."""
    buf = io.BytesIO()
    plot_fig.savefig(buf, format='png', bbox_inches='tight', dpi=DPI)
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode()
    container.markdown(
        f'<div style="text-align:center">'
        f'<img src="data:image/png;base64,{img_b64}" width="{width_px}"/>'
        f'</div>',
        unsafe_allow_html=True
    )


# Layout logic:
#   1 plot  → centered 50% ( narrow | plot | narrow )
#   2+ plots → NUM_COLS grid, like stock app individual charts
if len(plots) == 1:
    _, center_col, _ = st.columns([2, 2, 2])
    cell = center_col.container(border=True)
    cell.write("")
    render_centered(cell, plots[0], FIG_W_PX)
else:
    cols = st.columns(NUM_COLS)
    for i, plot_fig in enumerate(plots):
        cell = cols[i % NUM_COLS].container(border=True)
        cell.write("")
        render_centered(cell, plot_fig, FIG_W_PX)

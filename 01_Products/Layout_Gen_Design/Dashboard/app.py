import streamlit as st
import sys, os
# Add parent directory to path so 'Core' can be found
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import matplotlib.pyplot as plt
import io, base64

import importlib
import Core.Groups
importlib.reload(Core.Groups)
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
st.sidebar.header("Site Information")
site_width  = st.sidebar.slider("Plot Width (A)",  100, 1000, 400, step=10)
site_length = st.sidebar.slider("Plot Length (B)", 100, 1000, 300, step=10)
wind_dir = st.sidebar.selectbox("Wind Direction", ["North", "South", "East", "West"], index=2) # Default East

st.sidebar.divider()
st.sidebar.header("Manual Group Positions (m)")

st.sidebar.subheader("Power Block")
pb_w, pb_h = 120, 80
pb_def_x = max(0, min(site_width - pb_w, int((site_width - pb_w) / 2)))
pb_def_y = max(0, min(site_length - pb_h, int((site_length - pb_h) / 2)))
pb_x = st.sidebar.slider("PB X Pos", 0, max(0, site_width - pb_w), pb_def_x, step=5)
pb_y = st.sidebar.slider("PB Y Pos", 0, max(0, site_length - pb_h), pb_def_y, step=5)

st.sidebar.subheader("Cooling Tower")
ct_w, ct_h = 60, 80
ct_def_x = max(0, min(site_width - ct_w, site_width - ct_w - 10))
ct_def_y = max(0, min(site_length - ct_h, int((site_length - ct_h) / 2)))
ct_x = st.sidebar.slider("CT X Pos", 0, max(0, site_width - ct_w), ct_def_x, step=5)
ct_y = st.sidebar.slider("CT Y Pos", 0, max(0, site_length - ct_h), ct_def_y, step=5)

st.sidebar.subheader("Admin Building")
adm_w, adm_h = 50, 40
adm_def_x = max(0, min(site_width - adm_w, 20))
adm_def_y = max(0, min(site_length - adm_h, 20))
adm_x = st.sidebar.slider("Admin X Pos", 0, max(0, site_width - adm_w), adm_def_x, step=5)
adm_y = st.sidebar.slider("Admin Y Pos", 0, max(0, site_length - adm_h), adm_def_y, step=5)

# --- CORE ENGINE (Matplotlib image) ---
# High resolution rendering
FIG_W_PX, FIG_H_PX = 800, 600
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

# 2.5 Wind Direction Indicator
wind_config = {
    "North": ("↓ Wind (N)", site_width/2, site_length + 15, 'center', 'bottom'),
    "South": ("↑ Wind (S)", site_width/2, -15, 'center', 'top'),
    "East":  ("← Wind (E)", site_width + 15, site_length/2, 'left', 'center'),
    "West":  ("→ Wind (W)", -15, site_length/2, 'right', 'center')
}
w_text, w_x, w_y, w_ha, w_va = wind_config.get(wind_dir, wind_config["East"])
ax.text(w_x, w_y, w_text, color='#0078D7', fontsize=8, fontweight='bold', ha=w_ha, va=w_va, zorder=3)

# 3. Main Building Groups
groups = get_groups(
    site_width, site_length,
    pb_x=pb_x, pb_y=pb_y,
    ct_x=ct_x, ct_y=ct_y,
    adm_x=adm_x, adm_y=adm_y
)
for g in groups:
    draw_group(ax, g)

# --- Plot view configuration ---
# Extra padding at the bottom (-40) to make room for the legend inside the plot
ax.set_xlim(-30, site_width + 30)
ax.set_ylim(-40, site_length + 30)
ax.set_aspect('equal', adjustable='box')  # equal scale, box shrinks to fit

# Hide axis tick numbers (no x/y values shown)
ax.set_xticks([])
ax.set_yticks([])

# Remove the matplotlib axes spine (the extra black frame around the plot)
for spine in ax.spines.values():
    spine.set_visible(False)

# Legend placed inside the plot at the bottom empty space
ax.legend(loc='lower center', ncol=2, frameon=True, fontsize=8)
plt.tight_layout()

# --- DISPLAY CONFIG ---
NUM_COLS = 3      # ← change this freely: number of columns for multi-plot grid

# Collect all plots — add more figs here as new phases are built
plots = [fig, fig, fig]       # Phase 1: Site Boundary


def render_centered(container, plot_fig):
    """Render a matplotlib figure centered inside a Streamlit container responsively."""
    buf = io.BytesIO()
    plot_fig.savefig(buf, format='png', bbox_inches='tight', dpi=DPI)
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode()
    container.markdown(
        f'<div style="text-align:center">'
        f'<img src="data:image/png;base64,{img_b64}" style="max-width: 100%; height: auto;"/>'
        f'</div>',
        unsafe_allow_html=True
    )


# Layout logic:
#   1 plot  → centered 50% ( narrow | plot | narrow )
#   2+ plots → NUM_COLS grid, like stock app individual charts
if len(plots) == 1:
    _, center_col, _ = st.columns([1, 4, 1])  # Make center column much wider
    cell = center_col.container(border=True)
    cell.write("")
    render_centered(cell, plots[0])
else:
    cols = st.columns(NUM_COLS)
    for i, plot_fig in enumerate(plots):
        cell = cols[i % NUM_COLS].container(border=True)
        cell.write("")
        render_centered(cell, plot_fig)

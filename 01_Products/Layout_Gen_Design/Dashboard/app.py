import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import io, base64

# Font: Malgun Gothic (pre-installed on Windows, supports Korean)
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False  # Fix minus sign rendering with Korean fonts


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

# --- CORE ENGINE (Matplotlib image) ---
# Fixed pixel size: figsize × dpi = exact pixels on screen
# (8, 6) × 100 dpi = 800 × 600 px — never changes with browser scale
FIG_W_PX, FIG_H_PX = 500, 300
DPI = 100
fig, ax = plt.subplots(figsize=(FIG_W_PX / DPI, FIG_H_PX / DPI), dpi=DPI)

# 1. Site boundary
site_rect = patches.Rectangle(
    (0, 0), site_width, site_length,
    linewidth=0.8, edgecolor='black', facecolor='#f0f8ff', label='Site Boundary'
)
ax.add_patch(site_rect)

# 2. Road setback (5m inward from all edges)
setback = 5
if site_width > 2 * setback and site_length > 2 * setback:
    road_rect = patches.Rectangle(
        (setback, setback), site_width - 2 * setback, site_length - 2 * setback,
        linewidth=0.8, edgecolor='red', linestyle='--', facecolor='none',
        label='Primary Road Setback (5m)'
    )
    ax.add_patch(road_rect)

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
plots = [fig, fig]       # Phase 1: Site Boundary


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

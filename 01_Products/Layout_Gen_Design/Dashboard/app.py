import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Page configuration
st.set_page_config(page_title="PowerPlan AI", layout="wide")

st.title("⚡ PowerPlan AI: Layout Generator")
st.markdown("### Phase_01: Site Boundary & Primary Road Setback")

# --- UI CONTROLS (Sliders on the left) ---
st.sidebar.header("Site Dimensions (m)")
site_width  = st.sidebar.slider("Plot Width (A)",  100, 1000, 400, step=10)
site_length = st.sidebar.slider("Plot Length (B)", 100, 1000, 300, step=10)

# --- CORE ENGINE (Matplotlib image) ---
# Fixed pixel size: figsize × dpi = exact pixels on screen
# (8, 6) × 100 dpi = 800 × 600 px — never changes with browser scale
FIG_W_PX, FIG_H_PX = 800, 600
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
ax.legend(loc='upper right')
plt.tight_layout()

# --- DISPLAY — same container placement as streamlit_stock_app.py reference ---
# use_container_width=False → image renders at exact FIG_W_PX × FIG_H_PX, never scales
NUM_COLS = 3
cols = st.columns(NUM_COLS)
cell = cols[0].container(border=True)
cell.write("")                                # top padding (matches reference line 325)
cell.pyplot(fig, use_container_width=False)   # fixed 800×600 px, ignores page zoom

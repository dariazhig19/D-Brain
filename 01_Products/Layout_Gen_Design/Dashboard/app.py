import streamlit as st
import sys, os
# Add parent directory to path so 'Core' can be found
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import matplotlib.pyplot as plt
import io, base64

import importlib
import Core.Groups
import Core.Rules
importlib.reload(Core.Groups)
importlib.reload(Core.Rules)
from Core.Groups import get_groups, draw_group
from Core.Rules import evaluate_all

# Font: Malgun Gothic (pre-installed on Windows)
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False  # Fix minus sign rendering


# Page configuration
st.set_page_config(page_title="PowerPlan AI", layout="wide")

st.title("⚡ PowerPlan AI: Layout Generator")
st.markdown("### Phase_03: Rules Engine & Violation Alerts")

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

# 2.4 Gate House — fixed at bottom-center of site boundary (AD-02 reference)
GH_W, GH_H = 12, 8                          # Gate House footprint (12m × 8m)
gh_x = site_width / 2 - GH_W / 2           # centered on site width
gh_y = -GH_H                                # straddles the bottom boundary (y=0)
gh_pts_x = [gh_x,        gh_x + GH_W, gh_x + GH_W, gh_x,        gh_x]
gh_pts_y = [gh_y,        gh_y,         0,            0,            gh_y]
ax.fill(gh_pts_x, gh_pts_y, color='#5c4a32', alpha=0.85, zorder=2)
ax.plot(gh_pts_x, gh_pts_y, color='black',   linewidth=1.0, zorder=3)
ax.text(site_width / 2, gh_y - 2, "Gate House",
        ha='center', va='top', fontsize=6.5, color='#3a2e1e', fontweight='bold', zorder=4)


# 2.5 Wind Direction Indicator
wind_config = {
    "North": ("↓ Wind (N)", site_width/2, site_length + 15, 'center', 'bottom'),
    "South": ("↑ Wind (S)", site_width/2, -15, 'center', 'top'),
    "East":  ("← Wind (E)", site_width + 15, site_length/2, 'left', 'center'),
    "West":  ("→ Wind (W)", -15, site_length/2, 'right', 'center')
}
w_text, w_x, w_y, w_ha, w_va = wind_config.get(wind_dir, wind_config["East"])
ax.text(w_x, w_y, w_text, color='#0078D7', fontsize=8, fontweight='bold', ha=w_ha, va=w_va, zorder=3)

# 2.6 Scale Indicator (auto-computed)
# Figure physical width in mm → axis x-span covers (site_width + 60) data units
# 1 data unit = 1 m = 1000 mm in reality → scale = real_mm / drawn_mm
_fig_w_mm   = (FIG_W_PX / DPI) * 25.4          # e.g. 8 in × 25.4 = 203.2 mm
_axis_x_span = site_width + 60                  # xlim: -30 … site_width+30
_mm_per_unit = _fig_w_mm / _axis_x_span         # drawn mm per 1 m
_raw_scale   = 1000 / _mm_per_unit              # raw 1:N value
_std_scales  = [50, 100, 200, 250, 500, 1000, 2000]
_scale_denom = min(_std_scales, key=lambda s: abs(s - _raw_scale))
ax.text(site_width, site_length + 15, f"Scale  1 / {_scale_denom:,}",
        color='#333333', fontsize=9, fontweight='bold', ha='right', va='bottom', zorder=3)

# 3. Main Building Groups
groups = get_groups(
    site_width, site_length,
    pb_x=pb_x, pb_y=pb_y,
    ct_x=ct_x, ct_y=ct_y,
    adm_x=adm_x, adm_y=adm_y
)
for g in groups:
    draw_group(ax, g)

# --- PHASE 3: Rules Engine ---
scoring = evaluate_all(groups, site_width, site_length, wind_dir)
violations_by_group = scoring["violations_by_group"]

# RED violation overlay — draw on top of each failing group (zorder=4)
for g in groups:
    if violations_by_group.get(g["name"]):
        x, y, w, h = g["x"], g["y"], g["width"], g["height"]
        vx = [x,   x+w, x+w, x,   x]
        vy = [y,   y,   y+h, y+h, y]
        ax.plot(vx, vy, color='crimson', linewidth=2.5, linestyle='--', zorder=4)
        # Small violation badge above the building
        rule_ids = ", ".join(violations_by_group[g["name"]])
        ax.text(x + w/2, y + h + 3, f"⚠ {rule_ids}",
                ha='center', va='bottom', fontsize=6.5,
                color='crimson', fontweight='bold', zorder=5)

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

# --- DISPLAY ---

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

# Main plot — full width
plot_container = st.container(border=True)
render_centered(plot_container, fig)

# --- PHASE 3: Score Panel ---
st.divider()
total = scoring["total_penalty"]
results = scoring["results"]

# Top metric
passing = sum(1 for r in results if r["passed"])
failing = len(results) - passing

if total == 0:
    score_color = "normal"
else:
    score_color = "inverse"

col_score, col_pass, col_fail = st.columns(3)
col_score.metric("🏆 Total Penalty Score", f"{total:,.0f} pts",
                 delta=f"{failing} violation(s)" if failing else "All rules passed",
                 delta_color="inverse" if failing else "normal")
col_pass.metric("✅ Rules Passing", f"{passing} / {len(results)}")
col_fail.metric("❌ Rules Failing", str(failing))

st.markdown("#### Rule Results")
# Build results table as markdown
rows = []
for r in results:
    status = "✅ PASS" if r["passed"] else "❌ FAIL"
    penalty_str = f"{r['penalty']:,.0f} pts" if r["penalty"] > 0 else "—"
    rows.append(f"| **{r['id']}** | {r['name']} | {status} | {penalty_str} | {r['message']} |")

table_md = (
    "| ID | Rule | Status | Penalty | Detail |\n"
    "|:---|:-----|:------:|-------:|:-------|\n"
    + "\n".join(rows)
)
st.markdown(table_md)

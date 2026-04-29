import streamlit as st
import altair as alt
import pandas as pd

# Page configuration
st.set_page_config(page_title="PowerPlan AI", layout="wide")

st.title("⚡ PowerPlan AI: Layout Generator")
st.markdown("### Phase_01: Site Boundary & Primary Road Setback")

# --- UI CONTROLS (Sliders on the left) ---
st.sidebar.header("Site Dimensions (m)")
site_width = st.sidebar.slider("Plot Width (A)", 100, 1000, 400, step=10)
site_length = st.sidebar.slider("Plot Length (B)", 100, 1000, 300, step=10)

# --- CORE ENGINE (Geometry data) ---
setback = 5

# Build rectangle corner points as closed polygons (Altair needs explicit coords)
def make_rect_df(x0, y0, w, h, label):
    """Returns a DataFrame of the 5 corners that close a rectangle polygon."""
    return pd.DataFrame({
        "x": [x0, x0 + w, x0 + w, x0,       x0],
        "y": [y0, y0,      y0 + h, y0 + h,   y0],
        "layer": [label] * 5
    })

site_df    = make_rect_df(0,       0,       site_width,           site_length,           "Site Boundary")
setback_df = make_rect_df(setback, setback, site_width - 2*setback, site_length - 2*setback, "Road Setback (5m)")

plot_df = pd.concat([site_df, setback_df], ignore_index=True)

# --- CHART (same placement pattern as stock app reference) ---
# NUM_COLS grid → container(border=True) → altair_chart(use_container_width=True)
NUM_COLS = 1
cols = st.columns(NUM_COLS)

chart = (
    alt.Chart(plot_df)
    .mark_line()
    .encode(
        alt.X("x:Q", title="Width (m)").scale(domain=[-10, site_width + 10]),
        alt.Y("y:Q", title="Length (m)").scale(domain=[-10, site_length + 10]),
        alt.Color(
            "layer:N",
            scale=alt.Scale(
                domain=["Site Boundary", "Road Setback (5m)"],
                range=["black", "red"]
            ),
            legend=alt.Legend(orient="bottom")
        ),
        alt.StrokeDash(
            "layer:N",
            scale=alt.Scale(
                domain=["Site Boundary", "Road Setback (5m)"],
                range=[[1, 0], [6, 4]]   # solid vs dashed
            )
        ),
        alt.Order("x:Q"),  # draw lines in coordinate order
    )
    .properties(
        title=f"Site: {site_width}m × {site_length}m  |  Setback: {setback}m",
        height=500
    )
)

# --- DISPLAY — exact same pattern as the stock app reference ---
cell = cols[0 % NUM_COLS].container(border=True)
cell.write("")
cell.altair_chart(chart, use_container_width=True)

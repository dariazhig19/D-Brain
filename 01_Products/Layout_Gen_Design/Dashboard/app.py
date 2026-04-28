import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Настройка страницы
st.set_page_config(page_title="PowerPlan AI", layout="wide")

st.title("⚡ PowerPlan AI: Layout Generator")
st.markdown("### Phase 1: Site Boundary & Primary Road Setback")

# --- UI CONTROLS (Слайдеры слева) ---
st.sidebar.header("Site Dimensions (m)")
site_width = st.sidebar.slider("Plot Width (A)", 100, 1000, 400, step=10)
site_length = st.sidebar.slider("Plot Length (B)", 100, 1000, 300, step=10)

# --- CORE ENGINE (Отрисовка геометрии) ---
fig, ax = plt.subplots(figsize=(8, 6))

# 1. Рисуем границу участка (Site Boundary)
site_rect = patches.Rectangle((0, 0), site_width, site_length, 
                              linewidth=2, edgecolor='black', facecolor='#f0f8ff', label='Site Boundary')
ax.add_patch(site_rect)

# 2. Рисуем отступ для дороги (5m offset из правил Excel)
setback = 5
if site_width > 2*setback and site_length > 2*setback:
    road_rect = patches.Rectangle((setback, setback), site_width - 2*setback, site_length - 2*setback, 
                                  linewidth=1.5, edgecolor='red', linestyle='--', facecolor='none', 
                                  label='Primary Road Setback (5m)')
    ax.add_patch(road_rect)

# --- Настройка вида графика ---
ax.set_xlim(-50, site_width + 50)
ax.set_ylim(-50, site_length + 50)
ax.set_aspect('equal') # Чтобы квадраты не искажались
ax.set_xlabel("Width (m)")
ax.set_ylabel("Length (m)")
ax.grid(True, linestyle=':', alpha=0.6)
ax.legend(loc='upper right')

# --- DISPLAY (Вывод в Streamlit) ---
st.pyplot(fig)

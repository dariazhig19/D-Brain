import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.patches as patches

def setup_page():
    st.set_page_config(page_title="PowerPlan AI", page_icon="🚀", layout="wide")
    st.title("🚀 PowerPlan AI: Layout Generation Dashboard")
    st.markdown("---")

def draw_site(width: float, length: float):
    """Draws the site boundary using Matplotlib."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Create a Rectangle patch (Site Boundary)
    rect = patches.Rectangle(
        (0, 0), width, length, 
        linewidth=2, edgecolor='#1f77b4', facecolor='#e6f2ff'
    )
    ax.add_patch(rect)
    
    # Configure axes for better visualization
    ax.set_xlim(-width * 0.1, width * 1.1)
    ax.set_ylim(-length * 0.1, length * 1.1)
    ax.set_aspect('equal')
    ax.grid(True, linestyle='--', alpha=0.6)
    
    # Labels and title
    ax.set_title("Site Boundary Preview", fontsize=14, fontweight='bold', pad=15)
    ax.set_xlabel("Width (m)", fontsize=12)
    ax.set_ylabel("Length (m)", fontsize=12)
    
    return fig

def main():
    setup_page()
    
    # Sidebar Controls
    with st.sidebar:
        st.header("⚙️ Site Setup")
        st.write("Define the boundaries for the plot.")
        
        site_width = st.slider("Site Width (a)", min_value=50.0, max_value=1000.0, value=200.0, step=10.0)
        site_length = st.slider("Site Length (b)", min_value=50.0, max_value=1000.0, value=300.0, step=10.0)
        
        st.info("💡 Adjust the sliders to match the site requirements.")
    
    # Main Content Area
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Site Overview")
        st.metric(label="Total Area", value=f"{site_width * site_length:,.0f} m²")
        st.metric(label="Width (a)", value=f"{site_width} m")
        st.metric(label="Length (b)", value=f"{site_length} m")
    
    with col2:
        # Render Plot
        fig = draw_site(site_width, site_length)
        st.pyplot(fig)

if __name__ == "__main__":
    main()

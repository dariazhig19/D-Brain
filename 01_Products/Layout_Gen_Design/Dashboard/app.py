import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.patches as patches

def main():
    st.title("Layout_Gen_Design: System Ready")
    
    st.sidebar.header("Site Dimensions")
    site_width = st.sidebar.number_input("Site Width", min_value=0.0, value=10.0, step=1.0)
    site_height = st.sidebar.number_input("Site Height", min_value=0.0, value=20.0, step=1.0)
    
    st.write(f"### Visualizing Site: {site_width} x {site_height}")
    
    # Create plot
    fig, ax = plt.subplots()
    
    # Add rectangle
    rect = patches.Rectangle((0, 0), site_width, site_height, linewidth=2, edgecolor='r', facecolor='none')
    ax.add_patch(rect)
    
    # Set limits and aspect
    ax.set_xlim(-1, site_width + 1)
    ax.set_ylim(-1, site_height + 1)
    ax.set_aspect('equal')
    ax.set_title("Site Layout")
    ax.set_xlabel("Width")
    ax.set_ylabel("Height")
    
    st.pyplot(fig)

if __name__ == "__main__":
    main()

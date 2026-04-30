


### Phase_01: The Empty Plot.
#### Step_01: Make Dashboard

"Create a **Streamlit** dashboard application titled '**PowerPlan AI: Layout Generator**'.

**Requirements:**

1. **Page Config**: Set the layout to 'wide'.
2. **Header**: Include a main title with an emoji '⚡ PowerPlan AI: Layout Generator' and a sub-header '### Phase_01: Site Boundary & Primary Road Setback'.
3. **Sidebar Controls**: Create two sliders in the sidebar for 'Plot Width (A)' and 'Plot Length (B)' with a range from 100 to 1000 and a default value of 400 and 300 respectively.
4. **Core Visualization**:
    - Use **Matplotlib** to render a 2D geometry plot.
    - **Site Boundary**: Draw a solid black rectangle based on the slider inputs with a light blue fill color (#f0f8ff).
    - **Road Setback**: Implement a logic to draw a red dashed line rectangle representing a 5m internal setback from all sides of the boundary.
    - **Scaling**: Ensure the plot maintains an 'equal' aspect ratio and includes a small margin (padding) around the site boundary so it's not touching the edges of the plot.
5. **Style**: Use clean, professional English comments and labels throughout the code."


### Phase_02: The Three Giants
#### Step_01: Define and Render the Building Clusters

"Update the **PowerPlan AI** application to introduce the first 3 major building clusters: Power Block, Cooling Tower, and Admin Building.

**Requirements:**

1. **Core Engine Logic (`Core/Groups.py`)**:
    - Create a new module to define the groups as data dictionaries (name, x, y, width, height, color).
    - Calculate their default starting positions based on the site size:
        - **Power Block**: Center of the plot (Size: 120x80, Color: #4a90d9).
        - **Cooling Tower**: Right edge of the plot (Size: 60x80, Color: #7ed6a0).
        - **Admin Building**: Lower-left corner (Size: 50x40, Color: #f5a623).
    - Create a `draw_group(ax, group)` function that strictly uses explicit coordinate lists (`ax.plot()` and `ax.fill()`) instead of matplotlib patches, ensuring the geometry is future-ready for CAD line export.
2. **Dashboard UI (`Dashboard/App.py`)**:
    - Import the groups and render them inside the existing Matplotlib layout.
    - Add a new sidebar section 'Manual Group Offsets (m)'.
    - Create X and Y sliders (-200 to 200) for each of the 3 groups so the user can manually shift their positions to test the canvas limits.
3. **Architecture Rules**:
    - Keep strict separation of concerns: UI code stays in Dashboard, geometry data and logic stay in Core.
    - Ensure all python files use Capitalized naming conventions (`App.py`, `Groups.py`)."

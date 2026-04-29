


### Phase_01 — Environment Setup
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
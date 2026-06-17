# Phase 1: The Empty Plot — Implementation Plan

## Goal
Initialize the PowerPlan AI dashboard and render the basic site boundary and primary road setback using Streamlit and Matplotlib.

---

## Key Requirements

### 1. Project Structure
Create the foundational folder structure to separate concerns early:
- `Core/`: For future geometric and rule logic.
- `Dashboard/`: For the Streamlit UI (`App.py`).
- `Data/`: For Excel and JSON reference files.
- `Notes/`: For system documentation and roadmaps.

### 2. User Interface (Dashboard)
- Set up a `wide` layout Streamlit page titled "PowerPlan AI: Layout Generator".
- Add a sidebar to handle user inputs with two main sliders:
  - **Plot Width (A)**: 100 to 1000m (Default 400m, Step 10m)
  - **Plot Length (B)**: 100 to 1000m (Default 300m, Step 10m)

### 3. Core Engine (Geometry)
Use `matplotlib.pyplot` to generate the 2D plot based on the sliders.
- **Site Boundary**: Draw a solid black rectangle with a light blue fill (`#f0f8ff`) based on Width/Length.
- **Road Setback**: Draw a red dashed rectangle inset 5m from all boundaries, representing the mandatory primary road setback.
- Ensure the plot aspect ratio is `'equal'` so the drawing stays proportional and doesn't warp when dimensions change.

### 4. Display Logic
- Lock the visual resolution (e.g., 500x300 pixels) to prevent random browser scaling issues.
- Hide axis ticks, frames (spines), and coordinate values to give it a clean "canvas" appearance.
- Support local fonts (e.g., `Malgun Gothic`) to ensure any Korean text renders correctly on Windows without missing glyphs.

---

## Step-by-Step Build Sequence

1. **Initialize Environment**: Setup `.venv` and install `streamlit`, `matplotlib`.
2. **Create `Dashboard/App.py`**: Write the basic Streamlit layout, titles, and sidebar sliders.
3. **Draft Geometry**: Add the Matplotlib figure logic. Draw the site rectangle and the 5m setback rectangle dynamically using the slider variables.
4. **Refine Rendering**: Implement a custom render function using `base64` and HTML to center the Matplotlib image perfectly inside the Streamlit container.

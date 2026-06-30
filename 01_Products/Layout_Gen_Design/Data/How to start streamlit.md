# Install Python & Streamlit Environment

This guide explains how to install Python, set up a local virtual environment (`.venv`), install dependencies, and launch the Road Test Streamlit dashboard.

---

## Setup Steps

Follow these steps to configure your environment:

1. **Install Python 3.11**:
   Run the following command in PowerShell:
   ```powershell
   winget install Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
   ```
   *(Alternatively, you can download the installer from [python.org](https://www.python.org/downloads/). Ensure **"Add python.exe to PATH"** is checked during installation).*

2. **Create a Virtual Environment**:
   Initialize a local `.venv` inside your project root directory:
   ```powershell
   python -m venv .venv
   ```

3. **Install Dependencies**:
   Activate the virtual environment and install the required libraries:
   ```powershell
   .venv\Scripts\pip install streamlit matplotlib pandas openpyxl
   ```

---

## Launch the Dashboard

Open PowerShell and run the Streamlit command that matches **where your `.venv`
lives**. Run the command from the same folder that contains the `.venv`.

> [!IMPORTANT]
> In **this repository** the virtual environment is at the **repo root**
> (`D-Brain\.venv`) — there is **no** `.venv` inside `Layout_Gen_Design`.
> So use **Option A**. (Running `.venv\Scripts\streamlit …` from inside
> `Layout_Gen_Design` fails with *"module .venv could not be loaded"* because
> there is no `.venv` there.)

### Option A: From Repository Root  ← use this for this repo
Run from the repo root (the folder that holds `.venv`):
```powershell
cd e:\SKEE_LAYOUT\GitHub\D-Brain
.venv\Scripts\streamlit run 01_Products/Layout_Gen_Design/Dashboard/Road_Test.py
```

### Option B: From `Layout_Gen_Design` Directory Root
Only works if a `.venv` was created **inside** the `Layout_Gen_Design` folder
(e.g. a coworker copied/unzipped just that folder and made its own venv there):
```powershell
.venv\Scripts\streamlit run Dashboard/Road_Test.py
```

Streamlit will automatically open a tab in your web browser (usually at `http://localhost:8501`) displaying the interactive layout generator.


http://localhost:8501/
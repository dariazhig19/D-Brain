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

Open PowerShell in the directory where your project is located, and run the Streamlit command corresponding to your folder structure:

### Option A: From Repository Root
If you are running the program from the repository root directory, run:
```powershell
.venv\Scripts\streamlit run 01_Products/Layout_Gen_Design/Dashboard/Roads_Test.py
```

### Option B: From `Layout_Gen_Design` Directory Root
If you or a coworker are running the program directly from the `Layout_Gen_Design` folder (e.g. after copying/unzipping the folder), run:
```powershell
.venv\Scripts\streamlit run Dashboard/Roads_Test.py
```

Streamlit will automatically open a tab in your web browser (usually at `http://localhost:8501`) displaying the interactive layout generator.
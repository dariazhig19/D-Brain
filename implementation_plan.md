# Install Python & Streamlit Environment

This plan outlines the steps to install Python, set up a local virtual environment (`.venv`), install the necessary dependencies, and run the Road Test Streamlit dashboard.

## User Review Required

> [!IMPORTANT]
> - We will install Python 3.11 using Windows Package Manager (`winget`). This requires administrator privileges if not already configured for user-space installation, and may show a Windows user account control (UAC) prompt.
> - The installation might require you to restart your terminal or IDE if environment path variables do not update dynamically.

## Proposed Changes

We will perform system commands to set up the environment. No source files will be modified.

### Environment Setup Steps

1. **Install Python 3.11**:
   Run the winget install command:
   ```powershell
   winget install Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
   ```

2. **Create Virtual Environment**:
   Initialize `.venv` in the repository root:
   ```powershell
   python -m venv .venv
   ```

3. **Install Dependencies**:
   Activate the virtual environment and install the required libraries:
   ```powershell
   .venv\Scripts\pip install streamlit matplotlib pandas openpyxl
   ```

4. **Launch Dashboard**:
   Run the road test dashboard:
   ```powershell
   .venv\Scripts\streamlit run 01_Products/Layout_Gen_Design/Dashboard/Roads_Test.py
   ```

## Verification Plan

### Manual Verification
- We will verify that Python and pip are successfully installed and active in the `.venv`.
- We will run the Streamlit dashboard and provide the local URL to access it.

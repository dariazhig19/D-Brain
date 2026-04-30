# Skill: Update_Context_Files_Daily

## Purpose
This skill automates the synchronization between Daily Reports and Product Context files (`!Core_Context.md` and `!Dashboard_Context.md`). It ensures that every modification logged in a daily report is reflected in the corresponding "Daily Changes" table of the technical context files.

## Guidelines
- **Directory Scope**: 
    - Daily Reports: `04_Reports/Daily/Daily_Report_YYYYMMDD.md`
    - Core Context: `01_Products/*/Core/!Core_Context.md`
    - Dashboard Context: `01_Products/*/Dashboard/!Dashboard_Context.md`
- **Trigger**: Execute after a daily report is finalized and contains entries in the `🔗 Connected Notes (Modified Today)` table.

## Workflow

### 1. Analysis
- Open the latest `Daily_Report_YYYYMMDD.md`.
- Extract all rows from the `🔗 Connected Notes (Modified Today)` table.
- Categorize modifications by `Type`:
    - **Core**: Targets `!Core_Context.md`
    - **Dashboard**: Targets `!Dashboard_Context.md`

### 2. Update Logic (Per Category)
For each category (**Core**, **Dashboard**) that has modified notes:
1. **Identify Target File**: Locate the `!Context.md` file in the relevant subfolder (Core or Dashboard) of the active product.
2. **Collect Data**:
    - **Files**: Extract the `Note` column values. Format as a comma-separated list of code blocks (e.g., `` `Main.py`, `Geometry.py` ``).
    - **Change Summary**: Extract the `Change` column values. If multiple files are involved, combine them into a single, cohesive bullet point or sentence.
3. **Format Row**: Construct the table row:
   `| [[Daily_Report_YYYYMMDD]] | <Files> | <Change Summary> |`
4. **Apply Update**:
    - Check if a row for `[[Daily_Report_YYYYMMDD]]` already exists in the `📅 Daily Changes` table.
    - If it exists: Replace it with the new, comprehensive row.
    - If it doesn't: Append the new row to the end of the table.

## Technical Standards
- **Wikilinks**: Always use `[[Daily_Report_YYYYMMDD]]` format for dates to maintain Obsidian backlink integrity.
- **Surgical Edits**: Use targeted replacement to avoid disrupting other sections of the context files.
- **No Redundancy**: If no changes of type `Core` or `Dashboard` are found in the daily report, do not modify the context files.

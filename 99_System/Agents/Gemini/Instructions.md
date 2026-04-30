# Gemini Project Instructions

## Foundational Rules
- **Authority**: Always adhere to the project structure, distribution rules, and workflow defined in `!Atlas_System.md`.
- **Identity & Style**: Follow the "Vibe-Coding" philosophy, BIM-centric approach, and thinking patterns described in `!Me.md`.

## Workflow Mandates
- **Input Processing**: When analyzing or moving files from `00_Input`, strictly follow the Distribution Rules (01_Products, 02_Library, or 04_Reports).
- **Product Structure**: Maintain the mandatory subfolder structure for each product: `Core/`, `Dashboard/`, `Data/`, `Notes/`, and `Pipeline/`.
- **Reporting**: Every workday/session must conclude with a `Daily_Report_YYYYMMDD.md` in `04_Reports/Daily/`.
- **Context Management**: After writing a daily report, update relevant `!Core_Context.md` and `!Dashboard_Context.md` files according to the "Post-Report" logic in `!Atlas_System.md`.

## Technical & Design Standards
- **Core vs UI**: `Core/` logic must have zero Streamlit imports. `Dashboard/` calls `Core/` functions.
- **Scoring Logic**: Use additive scoring (lower = better) for all layout and design algorithms.
- **Phase Documentation**: Each phase in `Pipeline/` must contain exactly two files: `Phase XX Notes.md` and `Phase XX Output Example.png`.
- **Prompt Logging**: Log all significant LLM interactions in `02_Library/Prompts_Master/Prompt_History_Phase_XX.md`.

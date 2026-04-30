# Skill: Session_Wrapup

## Purpose
This skill executes the "Evening Workflow" to formally close a development session. It ensures that all temporary planning, context knowledge, daily logs, and product roadmaps are properly archived and synchronized across the D-Brain system before ending the day.

## Guidelines
- **Trigger**: Execute whenever the user types "lets wrapup" or explicitly requests to wrap up the session.
- **Dependencies**: This skill generates the daily report but intentionally **does not** update the `📅 Daily Changes` tables in the context files, as that is the specific responsibility of the `Update_Context_Files_Daily` skill.

## Workflow

### 1. Implementation Plan Archive
- Finalize today's Implementation Plan `.md`.
- Save or append it to the active phase folder (e.g., `01_Products/*/Pipeline/Phase_XX/Phase_XX_Plan.md`).

### 2. Daily Report Generation
- Generate today's Daily Report in `04_Reports/Daily/Daily_Report_YYYYMMDD.md`.
- Follow the standard `Daily Report Structure` defined in the `!Atlas_System.md` (Executive Summary, Project Progress, Issues & Blockers, Connected Notes).

### 3. Context File Deep-Update
- Extract the most important technical changes, architectural decisions, and new UI logic from the Implementation Plan.
- Inject these bullet points directly into the **body** of the relevant `!Core_Context.md` and `!Dashboard_Context.md` files.
- Place them under a heading matching the current phase (e.g., `**Phase_02 Implementations:**`).

### 4. Product Vision Sync
- Open `!Product_Vision.md`.
- Check off any completed tasks or phase goals.
- Update the "Current Status" to reflect the exact state of the project at the end of the day.

### 5. Handoff
- Remind the user (or automatically proceed if instructed) to run the `Update_Context_Files_Daily` skill so that the newly created Daily Report gets linked into the `📅 Daily Changes` tables of the context files.

# Atlas System: Knowledge & Product Map

This file defines the rules for processing information within the Product Incubator system.

---

## 📥 00_Input (The Inbox)
All raw ideas, code snippets, meeting notes, and business thoughts land here first. It is the "Buffer" zone.
- No subfolders. Files stay here only until analyzed.
- After analysis: move or transform into the correct destination folder.

---

## 🏗️ Distribution Rules (Vibe-Coding Workflow)
When a file is analyzed in `00_Input`, it must be transformed and moved:

### 1. To 01_Products (Project Specific)
- **Criteria**: If the content is a specific implementation, feature, or logic for a developing product.
- **Goal**: Turn the "draft" into a functional module within the product's step-by-step development.

### 2. To 02_Library (Engineering Standards)
- **Criteria**: If the content is a reusable principle, a Revit API cheat sheet, a core Python geometric function, or a refined AI prompt.
- **Goal**: Distill the "draft" into a clean, reusable engineering standard.

### 3. To 05_Reports (Execution Tracking)
- **Criteria**: End-of-day summaries, progress tracking, and strategic overviews.
- **Goal**: Maintain a historical log of decisions and development velocity.

---

## 🗺️ Full Vault Structure & Folder Rules

### 📁 01_Products — Active Product Development
Each product lives in its own subfolder (e.g., `Layout_Gen_Design/`).

Every product folder contains these subfolders:

| Subfolder | Purpose | What Goes Here |
|-----------|---------|----------------|
| `Core/` | Python engine logic | `.py` files (geometry, rules, orchestration). No UI code. One `!Core_Context.md` tracking file. |
| `Dashboard/` | Streamlit UI layer | `App.py` and any UI helpers. Calls Core functions only. One `!Dashboard_Context.md` tracking file. |
| `Data/` | Input data files | `.xlsx`, `.json`, `.csv` engineering requirements and reference data. |
| `Notes/` | Strategy & vision | `!Product_Vision.md` (roadmap), `!Scoring_Logic.md` (scoring rules), `Overview.canvas` (big picture map). |
| `Pipeline/` | Step-by-step dev log | One subfolder per phase. See Pipeline rules below. |

#### Pipeline Subfolder Rules
`Pipeline/` documents the development journey phase by phase.

| Subfolder | Purpose | What Goes Here |
|-----------|---------|----------------|
| `!Prototype/` | Early-stage ideas | Concept notes, workflow comparisons, initial reasoning before coding starts. |
| `Phase_01/`, `Phase_02/`, … | One folder per phase | **Exactly two files per phase**: a `.md` note describing the phase goals and decisions, and a `.png` image showing the visual output of that phase. |

**Naming rule for phase folders**: `Phase_XX` where XX is zero-padded (01, 02, 03…).
**Files inside a phase folder**: `Phase XX Notes.md` + `Phase XX Output Example.png`.

#### Core/ Note Rules
- `!Core_Context.md` must always reflect current file status and design principles.
- Add a row to its `📅 Daily Changes` table only when a Core file was modified that day.
- Design principles to maintain: zero Streamlit imports, additive scoring (lower = better), each `.py` file has a single responsibility.

#### Dashboard/ Note Rules
- `!Dashboard_Context.md` must always reflect the current UI state and slider parameters.
- Add a row to its `📅 Daily Changes` table only when a Dashboard file was modified that day.
- `st.set_page_config` must always be the first Streamlit call in `App.py`.

#### Notes/ Note Rules
- `!Product_Vision.md`: Update when the roadmap or phase status changes.
- `!Scoring_Logic.md`: Update when scoring dimensions or weights change.
- `Overview.canvas`: Visual overview — update when major architecture decisions happen.

---

### 📁 02_Library — Distilled Knowledge Base (The "Karpathy" Method)
Reusable, project-agnostic knowledge. Nothing product-specific goes here.

| Subfolder | Purpose | What Goes Here |
|-----------|---------|----------------|
| `Generative_Theory/` | Design principles | Notes on generative layout theory, spatial algorithms, academic references. |
| `Obsidian&Vibe Coding/` | Workflow methodology | Articles and notes on AI-augmented development, Obsidian systems, vibe-coding practices. |
| `Prompts_Master/` | Prompt engineering | `Prompt_History_Phase_XX.md` — one file per product phase, logging the exact prompts used and their outcomes. |
| `Templates/` | Vault templates | Reusable note templates. Currently: `Daily_Report_Template.md`. |

**Naming rule for prompt files**: `Prompt_History_Phase_XX.md` — mirrors the product's phase numbering.

---

### 📁 03_Assets — Visual Outputs & Reference Data
Stores generated and reference materials that support products but are not product code.

| Subfolder | Purpose | What Goes Here |
|-----------|---------|----------------|
| `References/` | External reference materials | Scanned docs, external PDFs, reference images from clients or standards. |
| `Visual_Outputs/` | Generated visualizations | Output diagrams, layout renders, exported images from development sessions. |

---

### 📁 04_Archive — Historical Versions
Completed development cycles, deprecated versions, old prototypes.
- No active editing. Files land here when a phase or product version is retired.

---

### 📁 05_Reports — Execution Tracking
| Subfolder | Purpose | What Goes Here |
|-----------|---------|----------------|
| `Daily/` | Daily reports | `Daily_Report_YYYYMMDD.md` — one file per workday. |

---

## 📊 Reporting Logic
1. **Trigger**: Every workday concludes with a `Daily_Report_YYYYMMDD.md` inside `05_Reports/Daily/`.
2. **Context**: Summarize active changes in `01_Products` and new standards in `02_Library`.
3. **Storage**: Reports are the "Memory" of the D-Brain — each links modified notes with their type and change summary.
4. **Post-Report**: After writing the daily report, update every `!Context.md` file (files with "context" in the name — currently `Core/!Core_Context.md` and `Dashboard/!Dashboard_Context.md`). Add a new row to the `📅 Daily Changes` table only if that folder's files were actually modified. If nothing changed in a folder, do not touch its context file.

---

## 📋 Daily Report Structure
| Section | Purpose |
|---------|---------|
| Executive Summary | 2–3 bullet overview of the day |
| Project Progress | Flat checklist — no project heading links |
| Issues & Blockers | Anything that slowed or blocked work |
| Connected Notes | Table: `Note · Type · Change` — one row per modified file |

### Note Types (Connected Notes)
| Type      | Used For                               |
| --------- | -------------------------------------- |
| Vision    | Product vision, roadmap, strategy docs (`!Product_Vision.md`) |
| Core      | Python engine files (`Core/`) |
| Dashboard | Python UI files (`Dashboard/`) |
| Logic     | Rules, scoring, algorithms (`!Scoring_Logic.md`) |
| Data      | Excel, JSON, CSV data files (`Data/`) |
| Prompt    | Prompt history and engineering notes (`Prompts_Master/`) |
| Pipeline  | Phase notes and output images (`Pipeline/Phase_XX/`) |
| Canvas    | Obsidian canvas files (`Overview.canvas`) |
| Template  | Vault templates (`Templates/`) |
| Context   | `!Context.md` folder reference files |
| Research  | Learning materials in `02_Library/Obsidian&Vibe Coding/` |

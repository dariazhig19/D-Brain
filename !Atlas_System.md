# Atlas System: Knowledge & Product Map

This file defines the rules for processing information within the Product Incubator system.

## 📥 00_Input (The Inbox)
All raw ideas, code snippets, meeting notes, and business thoughts land here first. It is the "Buffer" zone.

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

## 🗺️ System Map
- **01_Products**: Active development of commercial Add-ins.
- **02_Library**: Distilled knowledge base (The "Karpathy" Method).
- **03_Assets**: Visual outputs and data.
- **04_Archive**: Historical versions and completed cycles.
- **05_Reports**: Daily logs and executive summaries.
  - **05_Reports/Daily**: All daily reports stored as `Daily_Report_YYYYMMDD.md`.

## 📊 Reporting Logic
1. **Trigger**: Every workday concludes with a `Daily_Report_YYYYMMDD.md` inside `05_Reports/Daily/`.
2. **Context**: Summarize active changes in `01_Products` and new standards in `02_Library`.
3. **Storage**: Reports are the "Memory" of the D-Brain — each links modified notes with their type and change summary.

## 📋 Daily Report Structure
| Section | Purpose |
|---------|---------|
| Executive Summary | 2–3 bullet overview of the day |
| Project Progress | Flat checklist — no project heading links |
| Issues & Blockers | Anything that slowed or blocked work |
| Connected Notes | Table: `Note · Type · Change` — one row per modified file |

### Note Types (Connected Notes)
| Type | Used For |
|------|----------|
| Vision | Product vision, roadmap, strategy docs |
| Core | Python engine files (`Core/`) |
| Dashboard | Python UI files (`Dashboard/`) |
| Logic | Rules, scoring, algorithms |
| Data | Excel, JSON, CSV data files |
| Prompt | Prompt history and engineering notes |
| Canvas | Obsidian canvas files |
| Template | Vault templates |
| Context | `!Context.md` folder reference files |

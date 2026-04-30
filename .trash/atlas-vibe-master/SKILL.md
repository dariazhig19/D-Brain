---
name: atlas-vibe-master
description: Expert assistant for the Atlas System and Vibe-Coding workflow. Use when organizing BIM projects, managing the 00-05 folder structure, distilling engineering knowledge, or generating Daily Reports for the D-Brain project incubator.
---

# Atlas Vibe Master Skill

You are a specialized agent for the **D-Brain Product Incubator**. Your mission is to maintain the integrity of the **Atlas System** and apply **Vibe-Coding** principles.

## 🏗️ The Atlas System (Folder Management)

Always strictly follow the folder distribution logic:

- **00_Input**: The temporary buffer. Analyze and move files immediately.
- **01_Products**: Active development. Every product MUST have: `Core/`, `Dashboard/`, `Data/`, `Notes/`, `Pipeline/`.
- **02_Library**: Engineering standards and distilled knowledge (Karpathy method). No product-specific code.
- **03_Assets**: Supporting visuals and reference documents.
- **04_Reports**: Historical log of execution.

## 🚀 Vibe-Coding Principles

- **Logic First**: Understand the geometric and logic core before implementation.
- **BIM-Centric**: Focus on Revit API and AEC workflow automation.
- **Compaction**: Distill raw scripts into professional, compiled-ready code.
- **Clean Core**: `Core/` files must have zero Streamlit or UI imports.

## 📊 Reporting Workflow

Every session must end with a Daily Report:
1.  **File**: `04_Reports/Daily/Daily_Report_YYYYMMDD.md`.
2.  **Structure**: Executive Summary -> Project Progress -> Issues -> Connected Notes (Table).
3.  **Post-Action**: Update `!Core_Context.md` and `!Dashboard_Context.md` in modified product folders.

## 🛠️ Specialized Rules

- **Additive Scoring**: Lower values = better results in all algorithms.
- **Prompt History**: Log LLM prompts in `02_Library/Prompts_Master/Prompt_History_Phase_XX.md`.

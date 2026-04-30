# Skill: Topic_Shift_Backup

## Purpose
Prevents the loss of valuable Implementation Plans when the conversation topic changes abruptly. The AI's default system behavior is to overwrite the `implementation_plan.md` artifact for every new task within a single chat session. This skill forces the AI to buffer the old plan before generating a new one.

## Guidelines
- **Trigger**: Execute immediately BEFORE creating a *new* implementation plan if an old, unarchived plan currently exists in the artifact directory.
- **Condition**: If the user shifts the conversation (e.g., from "Phase 2 logic" to "Visual Dashboard updates") and a new plan is required.

## Workflow
1. **Detect**: Recognize that a new implementation plan is about to overwrite the existing one.
2. **Buffer**: Copy the contents of the current `implementation_plan.md`.
3. **Save**: Write the copied contents to the inbox: `00_Input/Backup_Plan_[Topic_Name].md` (e.g., `Backup_Plan_Phase_02.md`).
4. **Proceed**: Only after the backup is saved, safely overwrite the active `implementation_plan.md` artifact with the new task's plan.

## Integration with Session_Wrapup
At the end of the day, when `Session_Wrapup` is triggered, the AI will check `00_Input/` for any `Backup_Plan_*.md` files, move them to their permanent `Pipeline/Phase_XX/` folders, and delete the temporary backups.

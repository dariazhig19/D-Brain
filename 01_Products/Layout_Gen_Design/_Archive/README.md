# _Archive — frozen history

Nothing in here is part of the working system. Kept for reference only.

## Legacy_Pipeline_P05/
The previous (Phase 03–05) code pipeline, fully separate from the current
`Core/Layout06.py` + `Dashboard/Roads_Test.py` engine:
`app.py`, `main.py`, `rules.py`, `Roads.py`, `Exporter.py`, `RuleNetwork.py`,
plus the old context docs and the generated `Rule_Network.html`.

> These files use intra-package imports (`Core.Roads`, `Core.Rules`, `Core.Main`).
> From this archive location those imports **won't resolve** — the code is frozen,
> not runnable as-is. To revive any of it (e.g. the rule-scoring engine or the DXF
> exporter), move the needed module back under `Core/` and fix imports. The
> scoring rules themselves are documented in [`../PROJECT.md`](../PROJECT.md) §5.

## Docs/
Superseded documentation, consolidated into [`../PROJECT.md`](../PROJECT.md):
product vision (EN/KR), methodology & UX guide, scoring-logic SSoT, the Phase 06
structured plan, the 2026-05-14 session report, the Obsidian canvas, and the full
`Pipeline/` phase-history tree (Phase 01–06 notes + dashboard screenshots).

## Reference/
`streamlit_stock_app.py` — external Apache-licensed Streamlit sample kept as a
UI reference. Not project code.

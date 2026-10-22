# Instructions for Claude Code — Tripwise

This project uses spec-driven development. Everything is in one file, `SPEC.md`. Before doing anything, read:

1. **Part A — Constitution:** the rules. They override everything else.
2. **Part B — Product.**
3. The **Part C** feature you are working on: its Spec, Plan and Tasks subsections.

## Rules

- Work only on tasks listed in the current feature's Tasks subsection, in order. Do not start the next feature.
- Do not add features, endpoints, fields or dependencies that the spec does not ask for. If something seems missing, stop and say so instead of improvising.
- Do not edit `SPEC.md` except to tick finished tasks, unless asked. If the code cannot match the spec, stop and explain the conflict.
- Every task you finish: tick it in `SPEC.md` (`- [x]`), and mention the requirement IDs it served in the commit message.
- Write the acceptance tests named in the spec. A task is not finished until its tests pass.
- All tunable numbers go in `backend/tripwise/config.yaml`, never hard-coded.
- The LLM (Groq) must never produce or edit a plan; only the engine does (Constitution II).
- Never commit secrets. Read them from environment variables; add new names to `.env.example`.

## Environment

- Windows, VS Code, PowerShell (not WSL). Give commands in PowerShell syntax.
- Python 3.11+ in a virtual environment at `backend/.venv`.
- The repository root is `C:\dev\Project4`.

## Commit messages

- `feat(NNN): <task> [FR/ENG/DATA ids]`
- `test(NNN): <what> [ids]`
- `spec(<section>): <change> — <reason>`
- `chore: <what>`

---
name: spec
description: Plan a feature as a self-contained spec (spec.md and tasks.md) under specs/, or implement the next task of an approved spec. Use when the user asks to start a feature, write or revise a spec, or work on a spec task.
---

# Spec-driven work

The rules are in `AGENTS.md` (Spec-driven development, Token and cost hygiene). Templates and the roadmap are in `specs/README.md`.

## Phase A: planning (top-tier model)

1. Pick the spec from the roadmap. Work on a `spec/NNN-<name>` branch in a worktree (`make worktree name=NNN-<name> type=spec`).
2. Read `AGENTS.md`, `docs/design-decisions.md`, `docs/domain-conventions.md`, and `docs/modbus-map.md` when the pump is involved. Read existing code only where the feature touches it.
3. Write `spec.md`: requirements with EARS acceptance criteria (include failure cases), then the design: exact file paths, signatures and types, schemas, error handling, and verification commands. It must be enough to implement from without reading anything it does not list.
4. Write `tasks.md`: small test-first tasks, each with the requirement numbers it covers, the files it touches and the command that proves it. No manual or deployment tasks.
5. Run the `spec-reviewer` subagent once on both files. Give it the paths only. Fix or decline each finding. If it raised a blocker or major finding, ask the same reviewer once to check the fixes; anything still open goes to the user.
6. Set the status in `specs/README.md` to `planning`, then present both files to the user with a short note on what the reviewer raised and what you declined.
7. Stop. Write no application code. After approval the user starts a fresh session for execution.

## Phase B: execution (Sonnet)

1. Confirm the spec's status is `approved`. Work on a `feature/<topic>` branch in a worktree.
2. Read only `spec.md`, `tasks.md` and the files the spec lists. If that is not enough, stop and say what is missing.
3. Take the next unticked task. Write the failing test, then the code, then run the task's verification command.
4. Tick the task `[x]`. If the same failure happens twice, stop and report it in five lines or fewer.
5. When all tasks are ticked, run `make check`, then the `review-loop` skill, then ask the user before using `open-pr`.

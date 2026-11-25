---
name: spec
description: Create or advance a feature spec (requirements, design, tasks) under specs/, or implement the next task of an approved spec. Use when the user asks to start a feature, write or revise a spec, or work on a spec task.
---

# Spec-driven work

The process and roadmap are in `specs/README.md`. Read it first.

## Starting or advancing a spec

1. Pick the spec from the roadmap, or agree a new number and kebab-case name with the user. Work on a `spec/NNN-<name>` branch in a worktree (`make worktree name=NNN-<name> type=spec`).
2. Read `AGENTS.md` (safety rules), `docs/design-decisions.md`, `docs/domain-conventions.md` and, for anything touching the pump, `docs/modbus-map.md`.
3. Write only the next gate's document:
   - `requirements.md`: introduction, then numbered requirements, each with a user story and EARS acceptance criteria. Include failure cases (gateway down, bad reply, out-of-range command).
   - `design.md`: components and interfaces, data models, error handling, test strategy, correctness properties. Reference requirement numbers.
   - `tasks.md`: small test-first tasks, each listing the requirement numbers it covers. No task may be "deploy" or "test manually".
4. Run the `spec-reviewer` subagent on the document. Give it the file path and the spec folder only, not your reasoning. Fix or decline each finding and re-run it until it reports no blocker or major finding (three rounds at most, then escalate).
5. Present the document to the user with a short note: what the reviewer raised, what changed, what you declined and why. Do not start the next gate until they approve this one.
6. Update the status column in `specs/README.md`.

## Implementing a task

1. Confirm all three documents are approved. Work on a `feature/<topic>` branch in a worktree.
2. Take the next unticked task only. Write the failing test first, then the code.
3. Run `make check`.
4. Tick the task in `tasks.md`. If the spec turned out wrong, fix the spec in the same change.
5. When the tasks for the PR are done, run the `review-loop` skill, then ask the user for permission and use the `open-pr` skill.

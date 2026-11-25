# Specs

This project is spec-driven. A feature is designed and approved in writing before any of its code is written.

## Process

Each feature lives in `specs/NNN-<kebab-name>/` and moves through three gates. The user approves each one before the next starts.

| Gate | File | Content |
|---|---|---|
| 1. Requirements | `requirements.md` | Introduction, then numbered requirements. Each has a user story and EARS acceptance criteria (`WHEN <trigger> THE SYSTEM SHALL <response>`, `IF <condition> THEN THE SYSTEM SHALL ...`, `WHILE <state> ...`). |
| 2. Design | `design.md` | Overview, components and interfaces, data models, error handling, test strategy, and correctness properties suited to property-based tests. Cites the requirements it covers. |
| 3. Tasks | `tasks.md` | Numbered checklist of small, test-first coding tasks. Each task lists the requirement numbers it satisfies. |

Before a document goes to the user, the `spec-reviewer` subagent reviews it and its findings are resolved.

Implementation then proceeds one task at a time, on a branch in a worktree, ticking tasks off in `tasks.md` in the same PR as the code. Finished code goes through the review loop, then a pull request reviewed by GitHub Copilot and the user. The whole flow is in `docs/ways-of-working.md`.

Rules:

- A spec may not contradict `AGENTS.md` (safety rules) or `docs/design-decisions.md`. If it needs to, change those first, with the user's agreement.
- When implementation shows the spec was wrong, update the spec in the same PR.
- A spec settles open questions; move the answers into `docs/design-decisions.md`.

## Roadmap

Status values: `planned`, `requirements`, `design`, `tasks`, `in progress`, `done`.

| # | Spec | Purpose | Status |
|---|---|---|---|
| 001 | `001-readonly-probe` | A read-only command-line probe that reads every block through the gateway and prints raw and decoded values, to verify the map on the AXCR21V | planned |
| 002 | `002-modbus-client` | Async client: fixed block reads, request spacing, allowlisted writes with read-back, reconnect and backoff | planned |
| 003 | `003-config-and-state` | Config loading and validation, `AppState`, debounced persistence of settings to `config.yaml` | planned |
| 004 | `004-poll-loop` | Poll loop, immutable snapshots, command queue | planned |
| 005 | `005-mqtt-discovery-sensors` | MQTT client, device and discovery payloads, read-only sensors and fault reporting | planned |
| 006 | `006-mqtt-controls` | Power, operating mode, power mode and setpoint control from Home Assistant; climate entity | planned |
| 007 | `007-diagnostics` | Diagnostic entities: connection state, error counters, last-poll age, firmware and model, app version | planned |

Spec 001 comes first because every later spec depends on knowing the map is right for this pump.

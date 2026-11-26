# Specs

This project is spec-driven. A feature is designed and approved in writing before any of its code is written.

## Process

The rules are in `AGENTS.md` (Spec-driven development). In short: a planning session on the top-tier model writes the spec, the user approves it, and a fresh execution session on Sonnet implements it reading nothing else.

Each feature lives in `specs/NNN-<kebab-name>/` with two files:

| File | Content |
|---|---|
| `spec.md` | **Requirements**: numbered, each with a user story and EARS acceptance criteria (`WHEN <trigger> THE SYSTEM SHALL <response>`, `IF <condition> THEN ...`), covering edge cases and errors. **Design**: exact file paths to create or modify, function signatures and types, data schemas, error handling rules, and the exact verification commands. |
| `tasks.md` | Numbered checklist of small, test-first tasks. Each lists the requirement numbers it covers and the files it touches, and ends with the command that proves it. |

One gate: the `spec-reviewer` subagent reviews both files once, the author resolves its findings, and the user approves both together. Execution starts only after that, in a new session.

Rules:

- `spec.md` must be self-contained. If execution would need to read a file the spec does not list, the spec is incomplete.
- A spec may not contradict `AGENTS.md` (safety rules) or `docs/design-decisions.md`. If it needs to, change those first, with the user's agreement.
- When execution shows the spec was wrong, stop and correct the spec; do not improvise around it.
- A spec settles open questions; move the answers into `docs/design-decisions.md`.

## Roadmap

Status values: `planned`, `planning`, `approved`, `in progress`, `done`.

| # | Spec | Purpose | Status |
|---|---|---|---|
| 001 | `001-readonly-probe` | A read-only command-line probe that reads every block through the gateway and prints raw and decoded values, to verify the map on the AXCR21V | done |
| 002 | `002-modbus-client` | Async client: fixed block reads, request spacing, allowlisted writes with read-back, reconnect and backoff | planned |
| 003 | `003-config-and-state` | Config loading and validation, `AppState`, debounced persistence of settings to `config.yaml` | planned |
| 004 | `004-poll-loop` | Poll loop, immutable snapshots, command queue | planned |
| 005 | `005-mqtt-discovery-sensors` | MQTT client, device and discovery payloads, read-only sensors and fault reporting | planned |
| 006 | `006-mqtt-controls` | Power, operating mode, power mode and setpoint control from Home Assistant; climate entity | planned |
| 007 | `007-diagnostics` | Diagnostic entities: connection state, error counters, last-poll age, firmware and model, app version | planned |

Spec 001 comes first because every later spec depends on knowing the map is right for this pump.

# Agent instructions for the Fairland RS485 HA controller

A Docker service that bridges Fairland-built pool heat pumps to Home Assistant over the RS485 port on their control board. It is developed and verified on one unit, a TiLAB TurboSilence AXCR21V (a rebadged Fairland); other models on the same MWH216 / MWH298 boards are expected to work but are untested, so never claim support for them beyond what `README.md` says. It talks Modbus TCP to an RS485 gateway wired to the pump, and MQTT with discovery to Home Assistant. It is 100 % local: no cloud, no Tuya.

`CLAUDE.md` imports this file. Keep the instructions here so that every agent tool reads the same thing.

## Git policy

- **Never commit or push without explicit user permission.** Wait for approval before `git commit`, `git push`, or creating tags and PRs.
- **Never commit on `main`.** Work on a branch (`feature/<topic>`, `fix/<topic>`, `spec/<topic>`, `release/vX.Y.Z`) in a git worktree under `.claude/worktrees/`. Changes reach `main` only through a reviewed pull request.
- **Never push to `main`, force-push, or merge into `main`.** Push the branch and open a PR; the user merges.
- A hook (`.claude/settings.json` → `scripts/hooks/block_commit_on_main.sh`) blocks `git commit` and `git push` while on `main`.

## Heat pump safety rules

These protect real hardware. They override convenience.

1. **Write allowlist.** The app may write only: coil 0 (power) and holding registers 0–4 (operating mode, power mode, three setpoints). Service parameters (pump, defrost, expansion valve), forced defrost and factory reset are never written. Widening the allowlist needs an approved spec. The allowlist is pinned by `tests/unit/test_registers.py`.
2. **Unverified map.** The register map is not yet verified on the AXCR21V. Until the checks in `docs/modbus-map.md` (Verification) are filled in, nothing may write to the pump.
3. **Bus rules.** Fixed read shapes (48 bits, or 3 registers, from an allowed first address), at least 60 ms between requests, one master on the bus. See `docs/modbus-map.md`. One exception: the read-only probe may, when run with its extended flag, read the extended blocks listed there, which start on addresses the vendor does not label as allowed. The controller never does.
4. **Live hardware needs permission.** Any command that reaches the real pump or gateway, even read-only, needs the user's go-ahead in that session. Follow the `live-probe` skill.

## Spec-driven development

Planning and execution are separate phases, run in separate sessions on different models. No feature code without an approved spec.

### Phase A: planning (top-tier model, Fable)

- **Goal:** a self-contained spec, so that execution needs no guesswork and no exploration.
- **Output:** `specs/NNN-<name>/spec.md` and `specs/NNN-<name>/tasks.md`. Use the `spec` skill.
- **`spec.md` must contain:**
  - Requirements with EARS acceptance criteria, including edge cases and error handling.
  - Exact file paths to create or modify.
  - Explicit function signatures, input and output types, and data schemas.
  - The exact commands that verify completion.
- **`tasks.md`:** a numbered checklist of small, test-first tasks; each names the requirements it covers and the files it touches.
- **Do not write application code in this phase.** Stop once both files are saved and reviewed, so the user can approve them and run `/clear`.

### Phase B: execution (Sonnet)

- **Goal:** implement `tasks.md` in order with minimal token overhead.
- **Read only** the feature's `spec.md` and `tasks.md`, and the files the spec lists. Do not scan other directories. If the spec is not enough to proceed, stop and say what is missing; do not explore to fill the gap.
- **Checkpoint:** mark a task `[x]` in `tasks.md` when its verification command passes.
- When the tasks are done, run the `review-loop` skill, then ask the user before using `open-pr`.

### Review

Details are in `docs/ways-of-working.md`.

- **You do not review your own work.** The subagents in `.claude/agents/` do, each with its own pinned model and a fresh context. Give them the artefact, not your reasoning.
- **Planning:** one `spec-reviewer` pass on `spec.md` and `tasks.md` together before they go to the user.
- **Execution:** `code-reviewer` before a PR; `safety-reviewer` too when the change can reach the pump.
- **Rounds are capped:** one full review, then at most one follow-up in which the same reviewer checks only the fixes. A blocker or major finding still open after that goes to the user.
- **Findings** are fixed, declined with a reason, or deferred. The author cannot decline a blocker.
- **Pull request:** GitHub Copilot reviews it; handle its comments with `pr-feedback`. The user merges.

## Token and cost hygiene

- **Targeted reads.** Use grep or a line range when that is enough; do not read a whole large file.
- **Concise output.** Keep replies brief. Do not repeat file contents or explain obvious changes.
- **Fail fast.** If a test or build fails twice on the same issue, stop. Summarise the exact error and stack trace in five lines or fewer so the user can escalate to the planning model.
- **No unsolicited refactors.** Touch only what the active `spec.md` requires.
- **Subagents cost a full context each.** Start one only where this file calls for it, never to explore.

## Where knowledge lives

| What | Where |
|---|---|
| Register map, bus rules, write policy, verification status | `docs/modbus-map.md` (tables rendered from `app/modbus/registers.py`) |
| Units, signs, naming and MQTT conventions | `docs/domain-conventions.md` |
| Decisions and their reasons; open questions | `docs/design-decisions.md` |
| Review loops, roles, severities, definition of done, GitHub settings | `docs/ways-of-working.md` |
| Verification commands, worktrees, data handoff | `docs/dev-workflow.md` |
| Spec roadmap and templates | `specs/README.md` |
| Procedures | `.claude/skills/` (`spec`, `review-loop`, `open-pr`, `pr-feedback`, `modbus-register`, `live-probe`, `release`) |
| Reviewer subagents | `.claude/agents/` (`spec-reviewer`, `code-reviewer`, `safety-reviewer`) |

Read the relevant document before changing related code, and update it in the same PR when a fact or decision changes.

## Verification

Run `make check` before proposing a commit. It runs ruff, the Modbus map doc check and the tests with a coverage floor. Report failures with their output; do not weaken a test or the coverage floor to get green.

## Target architecture

Only `app/modbus/registers.py`, `codec.py` and `faults.py` exist today. The rest is the intended shape, to be confirmed by each spec's design.

```
Home Assistant  <--MQTT discovery/state/commands-->  app/ha/        MQTT client, entities, command parsing
                                                       |
                                                    app/state/     AppState (mutable), persisted fields
                                                       |
                                                    app/control/   poll loop, immutable snapshots
                                                       |
                                                    app/modbus/    register map, codec, faults, client
                                                       |  Modbus TCP
                                                 RS485 gateway  --RS485 Modbus RTU-->  heat pump (unit 1)
```

- `app/modbus/`: the register map is data; the codec is pure; the client owns block reads, request spacing, reconnect and backoff. No other module builds a Modbus request.
- `app/control/`: polls the pump on an interval, applies queued commands, builds an immutable snapshot for publishing.
- `app/ha/`: MQTT discovery, state publishing, command validation. A command is validated (type, range, allowed values) before it touches state or the pump.
- `app/state/` and `app/config.py`: runtime state; settings changed from Home Assistant are persisted to `config.yaml` and exposed as entities.
- Diagnostics (connection state, error counts, last-poll age, raw fault codes, firmware and model) are published as diagnostic entities.

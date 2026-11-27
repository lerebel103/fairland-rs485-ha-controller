# Agent instructions for the Fairland RS485 HA controller

A Docker service that bridges Fairland-built pool heat pumps to Home Assistant over the RS485 port on their control board: Modbus TCP to an RS485 gateway on one side, MQTT discovery on the other. 100 % local. Developed and verified on one unit, a TiLAB TurboSilence AXCR21V; never claim support for other models beyond `README.md`.

This file is the single source of agent instructions for Claude Code, Kiro and GitHub Copilot. `CLAUDE.md` imports it.

## Heat pump safety rules

These protect real hardware and override convenience.

1. **Write allowlist.** The app may write only coil 0 (power) and holding registers 0–4 (operating mode, power mode, three setpoints). Never write service parameters, forced defrost or factory reset. Widening the allowlist needs an approved OpenSpec change. `tests/unit/test_registers.py` pins it.
2. **Unverified map.** Until the Verification table in `docs/modbus-map.md` is filled in for the AXCR21V, nothing may write to the pump.
3. **Bus rules.** Fixed read shapes (48 bits or 3 registers) from allowed first addresses, at least 60 ms apart, one master. Details in `docs/modbus-map.md`. The one exception: the read-only probe's `--extended` flag.
4. **Live hardware needs permission.** Any command that reaches the real pump or gateway, even read-only, needs the user's go-ahead in that session. Follow `.claude/skills/live-probe/SKILL.md`.

## Git

- Never commit, push, tag or open a PR without explicit permission.
- Never commit to, push to, force-push or merge into `main`. Work on a branch in a worktree under `.claude/worktrees/` (`make worktree name=<topic>`); the user merges reviewed PRs.
- Stage files by name. Never stage `config.yaml`, `incoming/`, `.agents/` or a secret.
- Enforced, once you run `make hooks`, by `.pre-commit-config.yaml` (`no-commit-to-branch`), and in Claude Code by `.claude/settings.json`.

## How we work

Spec-driven with [OpenSpec](https://github.com/Fission-AI/OpenSpec): `openspec/specs/` is what is built, `openspec/changes/<name>/` is a change in flight (proposal, spec deltas, design, tasks). Full process: `docs/ways-of-working.md`. Do not invent another process.

| Phase | Session | Model role | Skill |
|---|---|---|---|
| Plan | own session | reasoning | `openspec-explore`, `openspec-propose` |
| Execute | fresh session | coding | `openspec-apply-change` |
| Close | after merge | any | `openspec-archive-change` |

Model roles are defined in `docs/ways-of-working.md` (Model roles): *reasoning* for planning, design and safety review; *coding* for implementation. Never name a model in this repo's docs; the maintainer picks one per role in the tool.
- **Plan:** write the change's artifacts, no application code, then stop for the user's approval.
- **Execute:** read only the change folder and the files its `design.md` lists. If that is not enough, stop and say what is missing. Tick a task when its verifying command passes.
- **Review:** you do not review your own work. Before a PR, run `code-reviewer` (and `safety-reviewer` when the change can reach the pump) once, from `.claude/agents/`; in other tools, paste the reviewer file into a fresh session. At most one follow-up round to check fixes.

## Cost rules

- Read with grep or a line range before opening a whole file. Do not scan directories the task does not name.
- Keep replies short. Do not repeat file contents or explain obvious changes.
- If a test or build fails twice on the same issue, stop and summarise the error in five lines or fewer.
- No unrequested refactors. Touch only what the active change requires.
- Subagents cost a full context each. Start one only where this file says to, never to explore.
- Run `/clear` (or open a new session) between phases.

## Verification

`make check` before proposing a commit (ruff, Modbus map doc check, tests with a coverage floor). Report failures with their output; never weaken a test or the coverage floor to get green.

## Where knowledge lives

| What | Where |
|---|---|
| Register map, bus rules, write policy, verification status | `docs/modbus-map.md` (tables rendered from `app/modbus/registers.py`) |
| Units, signs, naming, MQTT conventions | `docs/domain-conventions.md` |
| Decisions and open questions | `docs/design-decisions.md` |
| Intended code structure | `docs/architecture.md` |
| Planned changes | `docs/roadmap.md` |
| Process, review, PRs, repository settings | `docs/ways-of-working.md` |
| Commands, worktrees, data handoff, CI | `docs/dev-workflow.md` |
| Behaviour that is built | `openspec/specs/` |
| Hardware procedures | `.claude/skills/` (`live-probe`, `modbus-register`, `release`) |

Read the relevant document before changing related code. Update it in the same PR when a fact or decision changes.

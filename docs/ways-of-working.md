# Ways of working

How a change goes from an idea to a merged pull request. It applies to humans and agents, in Claude Code, Kiro and GitHub Copilot alike. The spec process is [OpenSpec](https://github.com/Fission-AI/OpenSpec); this page only adds what is specific to this project.

## Roles

| Role | Who | Does |
|---|---|---|
| Maintainer | the user | Approves each plan, permits commit, push and PR, merges |
| Author | the agent session | Plans, implements, triages review findings. Never merges, never the final reviewer of its own work |
| Reviewers | `.claude/agents/code-reviewer.md`, `safety-reviewer.md`, each read cold | Report findings. Never edit, commit, or touch the pump |
| Copilot | GitHub Copilot code review on the PR | Independent second review |
| CI | GitHub Actions | `make check` equivalent, Docker build |

## Lifecycle

```
PLAN     own session, reasoning model        -> maintainer approves the artifacts
EXECUTE  fresh session, coding model           -> tasks ticked, make check green
REVIEW   code-reviewer (+ safety-reviewer)    -> findings triaged, one follow-up at most
PR       maintainer permits; CI + Copilot     -> maintainer merges
CLOSE    archive the change                   -> openspec/specs/ updated
```

OpenSpec skills (Claude Code and Kiro list them as `/openspec-*`; Copilot in VS Code reads `.claude/skills/`; the spelling may differ per tool):

| Step | Skill | Notes |
|---|---|---|
| Think | `openspec-explore` | Optional. No files written |
| Plan | `openspec-propose <name>` | Creates `openspec/changes/<name>/` with `proposal.md`, `specs/`, `design.md`, `tasks.md` |
| Execute | `openspec-apply-change` | Implements `tasks.md` in order |
| Close | `openspec-archive-change` | Merges the deltas into `openspec/specs/` and moves the change to `archive/` |

`openspec/config.yaml` carries the project context and per-artifact rules, so the agent gets them without extra prompting. Change names are kebab-case, without numbers; the order is in `docs/roadmap.md`.

### 1. Plan

Branch and worktree first (`make worktree name=<name> type=spec`). Use the reasoning model; this is the one phase where its higher cost pays off, because a complete design lets a cheaper model execute without exploring.

1. Run `openspec-propose`. The `design.md` must be execution-ready: exact paths, signatures, schemas, error handling, the files to read, and verification commands (rules in `openspec/config.yaml`).
2. Run `openspec validate <name> --strict`.
3. If the change can reach the pump, ask `safety-reviewer` to read `design.md` once.
4. Present the artifacts to the maintainer. Stop. No application code in this phase. The maintainer approves, then the session ends.

### 2. Execute

New session, coding model, `openspec-apply-change`. It reads the change folder and the files `design.md` lists, and nothing else. Per task: failing test, code, the task's verifying command, tick. If the design is wrong, fix the design in the same branch and say so in the PR. If execution is stuck after two attempts at the same failure, stop and escalate to the plan model with a five-line summary.

### 3. Review

1. `make check` must be green.
2. Run `code-reviewer` always, and `safety-reviewer` when the diff touches `app/modbus/`, `app/control/`, command handling in `app/ha/`, scripts that open a connection, or `docs/modbus-map.md`. Give each only the worktree path, branch, change name and diff base (the PR's target branch, `main` unless the change is stacked). In Claude Code they run as subagents; elsewhere paste the reviewer file into a fresh session.
3. Triage every finding (below) and fix what is accepted.
4. If a blocker or major finding was raised, the same reviewer checks the fixes once. No third round: what is still open goes to the maintainer with both positions.
5. Save reports under `.agents/reviews/<branch>/` (local) and put a short summary in the PR description.

### 4. Pull request

With the maintainer's permission: commit (prefix `feat`, `fix`, `docs`, `test`, `chore`, `ci`, `spec`), push the branch, open the PR against `main` (or the parent feature branch for a stacked change) using `.github/pull_request_template.md`. Link the change folder and include the review summary. Copilot is requested automatically.

Handle review comments by fetching them with `gh pr view <n> --comments` and `gh api repos/{owner}/{repo}/pulls/<n>/comments`. Check each against the code and the spec, since Copilot has not read the spec. Triage, fix test-first, and if a fix touches code that can reach the pump, run `safety-reviewer` on it again. Show the maintainer the diff, push with permission, reply to every thread and resolve it. A comment that exposes a gap in the design is fixed in the design too.

### 5. Close

After merge, run `openspec-archive-change`, update `docs/roadmap.md`, and move any settled question in `docs/design-decisions.md` to Decided.

## Model roles

Work is split by the kind of thinking it needs, not by product name. Documents, skills and prompts in this repo name only a role; the maintainer binds each role to a model in the tool, and rebinding it is the only change needed when models change.

| Role | Used for | Why |
|---|---|---|
| reasoning | Exploring, `openspec-propose` (design), `safety-reviewer`, deciding what to do when execution is stuck | Mistakes here are expensive and compound; a stronger, costlier model pays for itself |
| coding | `openspec-apply-change`, fixing review findings, `code-reviewer`, `openspec-archive-change` | The design already settles the decisions, so a cheaper, faster model is enough |

The only place a model is named is each tool's own setting:

- Claude Code: `model:` in the front matter of `.claude/agents/*.md` (use an alias such as `opus` or `sonnet`, which follow the latest version, or `inherit`), and `/model` for the session.
- Kiro and Copilot: the chat model picker, per session.

Rule of thumb: if a coding-role session hits the same failure twice, escalate with a five-line summary to a reasoning-role session rather than retrying.

## Findings

| Severity | Meaning | Effect |
|---|---|---|
| blocker | Breaks a safety rule, loses data, can harm the pump, or contradicts an approved scenario | Must be fixed. Only the maintainer can overrule |
| major | A bug, an untested scenario, a missing error path, a departure from the design | Fixed, or declined with a written reason |
| minor | Maintainability, naming, duplication, weak test | Fixed if cheap, else noted |
| nit | Taste | Optional |

Outcomes are fixed, declined (with the reason) or deferred (with where it is tracked). Decline a finding when it is wrong, out of scope, or contrary to `AGENTS.md` or `docs/design-decisions.md`. "It works" is not a reason.

## What reviewers check

**Every change**

- Each behaviour traces to a scenario, and each scenario in scope has a test that would fail without the code.
- Error paths: gateway unreachable, timeout, short or malformed reply, Modbus exception, MQTT disconnect, invalid command.
- Tests assert behaviour; none weakened or deleted; coverage floor untouched.
- No secrets or site-specific addresses outside `config.yaml.example`; nothing staged from `incoming/` or `.agents/`.
- Docs changed with the facts. The smallest change that satisfies the task.

**When the pump is in reach**

- No write outside the allowlist; every write goes through `codec.encode` and is read back.
- No write path reachable while the map is unverified.
- Reads use fixed block shapes from allowed first addresses (the probe's `--extended` blocks in `docs/modbus-map.md` are the one exception); requests serialised and at least 60 ms apart; only the Modbus client builds requests.
- Home Assistant commands are validated (type, range, allowed values) before they reach state or the pump.
- Failure leaves the pump alone: no retry storm, bounded backoff, no write replayed after a reconnect without re-reading state.

## Definition of done

- All tasks ticked and the change's design matches what was built.
- `make check` green locally and CI green.
- Review ended clean and its summary is in the PR description.
- Every review thread has a reply and is resolved.
- The maintainer merged; the change is archived.

## Repository settings

Set once on GitHub by the maintainer.

1. **Branch ruleset for `main`**: import `.github/rulesets/main.json` (Settings → Rules → Rulesets → Import) or `gh api repos/{owner}/{repo}/rulesets --method POST --input .github/rulesets/main.json`. It requires a PR, resolved threads and the `lint`, `test` and `build` checks, and blocks force pushes and deletion. Zero approving reviews are required, because GitHub does not let an author approve their own PR.
2. **Copilot code review**: enable "Automatically request Copilot code review" in the same ruleset (needs a Copilot plan with code review).
3. **Copilot's instructions**: `.github/copilot-instructions.md`. Keep it in step with `AGENTS.md`.
4. **Secrets**: `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` for the build workflow.

## Tool setup

OpenSpec needs Node 22.20+ (`npm i -g @fission-ai/openspec`, or `npx @fission-ai/openspec`). Skills are committed under `.claude/skills/` and `.kiro/skills/`, so nothing needs installing to follow the process. After upgrading OpenSpec, run `openspec update`. Pick the model per phase as described in Model roles.

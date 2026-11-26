# Ways of working

How a change goes from an idea to a merged pull request, who reviews it at each stage, and what "good enough to move on" means. It applies to humans and agents alike.

## Roles

| Role | Who | Does | Never does |
|---|---|---|---|
| Maintainer | the user | Approves each spec, gives permission to commit, push and open a PR, merges | |
| Author | the main agent session | Writes specs, tests and code; triages and fixes review findings | Reviews its own work as the final word; merges |
| Reviewers | subagents in `.claude/agents/`, each with a pinned model (Sonnet; Opus for safety) and a fresh context | Read the change cold and report findings | Edit files, commit, or talk to the pump |
| Copilot | GitHub Copilot code review on the PR | Independent second review from a different model | |
| CI | GitHub Actions | Lint, map doc check, tests with coverage floor, Docker build | |

The author and the reviewer are always different contexts. A reviewer is given the artefact and the documents it must satisfy, not the author's reasoning, so that it cannot simply agree.

## Lifecycle

```
 planning session (top-tier model)
   spec.md + tasks.md -> one spec-reviewer pass -> maintainer approval -> /clear
 execution session (Sonnet), per task
   failing test -> code -> make check -> tick task
 pre-PR
   review loop (code-reviewer, plus safety-reviewer when the pump is in reach) -> clean
   maintainer permission -> commit, push, open PR
 pull request
   CI + Copilot review -> pr-feedback loop -> maintainer review -> maintainer merges
```

### 1. Planning

Done in a planning session on the top-tier model. No application code is written.

1. The author drafts `spec.md` and `tasks.md` (`spec` skill).
2. The `spec-reviewer` subagent reviews both once. The author fixes or declines each finding.
3. If there were blocker or major findings, the same reviewer is asked once to check only the fixes.
4. The author presents both files to the maintainer with a short note: what the reviewer raised, what changed, what was declined and why.
5. The maintainer approves, or asks for changes. Then the session ends; execution starts in a fresh one.

### 2. Implementation

Done in an execution session on Sonnet that reads only the spec, the tasks and the files the spec lists. One task from `tasks.md` at a time, on a branch in a worktree: failing test first, then code, then `make check`, then tick the task. If the code shows the spec was wrong, the spec is corrected in the same branch and the change is called out in the PR.

### 3. Pre-PR review loop

Before asking the maintainer for permission to open a PR, the author runs the `review-loop` skill:

1. `make check` must be green.
2. Reviewers run in parallel on the branch diff against `main`:
   - `code-reviewer`: always.
   - `safety-reviewer`: when the diff touches `app/modbus/`, `app/control/`, command handling in `app/ha/`, `scripts/` that open a connection, or `docs/modbus-map.md`.
3. The author triages every finding (see below) and fixes what is accepted.
4. If there were blocker or major findings, each reviewer that raised one is asked once to check only the fixes, in its existing context. There is no third round: anything still open at blocker or major level goes to the maintainer with both positions.

### 4. Pull request

1. With the maintainer's permission, the author commits, pushes the branch and opens the PR (`open-pr` skill). The PR description follows `.github/pull_request_template.md` and includes the review summary.
2. CI runs. Copilot is requested as a reviewer automatically (see [Repository settings](#repository-settings)).
3. The author handles Copilot and human comments with the `pr-feedback` skill: triage, fix on the branch, reply to every thread, resolve it. New commits need the maintainer's permission like any other.
4. The maintainer reviews and merges. Agents never merge.

## Findings

Reviewers report each finding with a severity, a location, the concrete failure it would cause, and a suggested fix.

| Severity | Meaning | Effect |
|---|---|---|
| blocker | Breaks a safety rule, loses data, can harm the pump, or contradicts an approved requirement | Must be fixed. Cannot be declined by the author; only the maintainer can overrule |
| major | A bug, an untested requirement, a missing error path, or a design departure from the spec | Fixed, or declined with a written reason the maintainer sees |
| minor | Maintainability, naming, duplication, a weak test | Fixed if cheap; otherwise noted |
| nit | Taste | Optional |

Triage outcomes are **fixed**, **declined** (with the reason) or **deferred** (with where it is tracked). The record of each round is kept in `.agents/reviews/` (local), and the summary goes into the PR description so the maintainer and Copilot see what was already considered.

A finding is declined when it is wrong, out of scope for the spec, or contrary to `AGENTS.md` or `docs/design-decisions.md`. "It works" is not a reason.

## What reviewers check

**Every code change**

- Each changed behaviour traces to a requirement, and each acceptance criterion in scope has a test that would fail without the code.
- Error paths: gateway unreachable, timeout, short or malformed reply, Modbus exception, MQTT disconnect, invalid command from Home Assistant.
- Tests assert behaviour, not implementation; no test weakened or deleted to get green; coverage floor untouched.
- No secrets, no site-specific addresses outside `config.yaml.example`, nothing staged from `incoming/` or `.agents/`.
- Docs changed with the facts: `docs/modbus-map.md`, `docs/design-decisions.md`, `docs/domain-conventions.md`, `AGENTS.md`.
- The change is the smallest that satisfies the task; no unrelated refactoring.

**When the pump is in reach (safety review)**

- No write outside the allowlist; every write goes through `codec.encode` and is read back.
- No write path is reachable while the map is unverified for the AXCR21V.
- Reads use the fixed block shapes and allowed first addresses (the probe's opt-in extended blocks in `docs/modbus-map.md` are the one exception); requests are serialised and at least 60 ms apart; only the Modbus client builds requests.
- Home Assistant commands are validated (type, range, allowed values) before they reach state or the pump.
- Failure leaves the pump alone: no retry storm, bounded backoff, no write replayed after a reconnect without re-reading state.

**Specs**

- Requirements are testable EARS statements, cover failure cases, and do not contradict the safety rules or recorded decisions.
- The design covers every requirement and is execution-ready: exact file paths, signatures and types, schemas, error handling, and verification commands. Nothing is left for the implementer to discover.
- Tasks are small, test-first, ordered so each leaves `make check` green, and every requirement is covered by at least one task.

## Definition of done for a PR

- All tasks in scope are ticked, and the spec matches what was built.
- `make check` is green locally and CI is green on the PR.
- The review loop ended clean, and its summary is in the PR description.
- Every Copilot and human review thread has a reply and is resolved.
- The maintainer has reviewed and merges.

## Repository settings

These are set once on GitHub by the maintainer. They make the process above enforceable instead of a convention.

1. **Branch ruleset for `main`**: import `.github/rulesets/main.json` (Settings → Rules → Rulesets → New ruleset → Import), or run `gh api repos/{owner}/{repo}/rulesets --method POST --input .github/rulesets/main.json`. It requires a pull request, resolved review threads, and the `lint`, `test` and `build` checks, and blocks force pushes and deletion. It asks for zero approving reviews, because PRs are opened from the maintainer's own account and GitHub does not let an author approve their own PR.
2. **Copilot code review**: in the same ruleset, enable "Automatically request Copilot code review", including on new pushes. This needs a Copilot plan that includes code review.
3. **Copilot's instructions**: `.github/copilot-instructions.md` tells Copilot the safety rules and what to look for. Keep it in step with `AGENTS.md`.
4. **Secrets**: `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` for the build workflow.

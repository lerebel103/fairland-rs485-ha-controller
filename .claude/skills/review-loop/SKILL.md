---
name: review-loop
description: Run the independent review loop on the current branch (code-reviewer, plus safety-reviewer when the pump is in reach) and iterate until it is clean. Use when implementation of a task or spec is finished and before asking to open a PR, or when the user asks for a review of the branch.
---

# Review loop

The rules are in `docs/ways-of-working.md` (Pre-PR review loop, Findings). This is the procedure.

1. Run `make check`. Fix anything red before involving a reviewer.
2. Decide which reviewers apply. `code-reviewer` always. `safety-reviewer` when `git diff --name-only main...HEAD` touches `app/modbus/`, `app/control/`, `app/ha/`, `scripts/` or `docs/modbus-map.md`.
3. Start the reviewers as subagents, in parallel. Give each one only: the worktree path, the branch name, and the spec folder. Do not give them your reasoning, your summary of the change, or what you expect them to find.
4. Save each report verbatim to `.agents/reviews/<branch>/round-<n>-<reviewer>.md`.
5. Triage every finding as fixed, declined (with the reason) or deferred (with where it is tracked). You may not decline a blocker; take it to the user instead. Check each finding against the code before acting on it, because reviewers can be wrong.
6. Fix the accepted findings test-first and run `make check`.
7. If a reviewer raised a blocker or major finding, message that same reviewer once and ask it to check only the fixes. Do not start a fresh reviewer and do not run a third round. Anything still open at blocker or major level goes to the user with both positions.
8. Write `.agents/reviews/<branch>/summary.md`: rounds run, findings by severity, what was fixed, what was declined and why. This goes into the PR description.
9. Report to the user: the verdicts, the summary, and anything they need to decide. Do not commit or open the PR without their permission.

Specs are reviewed once by the `spec-reviewer` subagent under the same cap; the `spec` skill calls it.

---
name: pr-feedback
description: Triage and address GitHub Copilot and human review comments on a pull request with the gh CLI. Use when the user says there are comments on the PR, or a Copilot review has landed.
---

# PR feedback

1. Fetch everything: `gh pr view <n> --comments`, `gh api repos/{owner}/{repo}/pulls/<n>/comments` (inline) and `gh api repos/{owner}/{repo}/pulls/<n>/reviews`. Copilot's review appears as a review with inline comments.
2. Triage each comment as fixed, declined or deferred, using the severity table in `docs/ways-of-working.md`. Check it against the code first: Copilot can be wrong, and it has not read the spec. A comment that contradicts the spec, the safety rules in `AGENTS.md` or `docs/design-decisions.md` is declined with that reference. Record the triage in `.agents/reviews/<branch>/pr-feedback.md` (local).
3. Fix the accepted ones on the PR branch, test-first. No history rewrite. If a fix touches code that can reach the pump, run the `safety-reviewer` again.
4. Run `make check`.
5. Show the user the triage and the diff. Commit and push only with their permission.
6. After the push, reply to every thread (what changed and in which commit, or why it was declined) and resolve it. Leave a thread open only when the user needs to decide.
7. If a comment exposed a gap in the spec or a recurring mistake, fix the spec or add the rule to `docs/ways-of-working.md` or `.github/copilot-instructions.md` in the same PR.

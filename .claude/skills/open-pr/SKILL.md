---
name: open-pr
description: Commit, push and open a pull request for the current branch, with the spec links and review summary in the description. Use when the user gives permission to raise a PR.
---

# Open a pull request

1. **Preconditions.** Stop and say which one fails if any does:
   - The branch is not `main`, and the work is in a worktree under `.claude/worktrees/`.
   - `make check` is green.
   - The review loop ended clean and `.agents/reviews/<branch>/summary.md` exists (`review-loop` skill).
   - The tasks in scope are ticked in `tasks.md`, and the spec matches the code.
   - The user has given permission to commit and push in this session.
2. **Stage by name.** Never `git add -A`. Never stage `config.yaml`, `incoming/`, `.agents/` or a secret. Show `git status --short` and the staged file list.
3. **Commit** with a conventional prefix (`feat`, `fix`, `docs`, `test`, `chore`, `ci`, `spec`) and a body that says why.
4. **Push** the branch: `git push -u origin <branch>`. Never push to `main`, never force-push.
5. **Open the PR** with `gh pr create --base main`, filling in every section of `.github/pull_request_template.md`: the spec and requirement numbers, what changed, how it was verified, the review summary, and what the reviewer should look at hardest. State plainly anything that was not tested or was deferred.
6. **After opening**: confirm CI started and that Copilot was requested as a reviewer (`gh pr view <n> --json reviewRequests`). If it was not, tell the user; the repository setting is described in `docs/ways-of-working.md`.
7. Hand over to the `pr-feedback` skill when comments arrive. Do not merge.

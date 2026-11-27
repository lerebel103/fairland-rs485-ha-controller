# Dev workflow

## Setup

```
uv sync --group dev
make hooks        # installs the pre-commit hooks (ruff, and no commits on main); once per clone
```

## Verification

Run from the repo root or from a worktree. Each worktree gets its own `.venv` on first `uv run`.

```
make check        # ruff check, ruff format --check, Modbus map doc check, tests with coverage
make format       # apply formatting and safe lint fixes
make modbus-map   # re-render docs/modbus-map.md after changing app/modbus/registers.py or faults.py
```

## Worktrees

All work happens in a worktree under `.claude/worktrees/` (gitignored), one per branch.

```
make worktree name=<topic>              # branch feature/<topic>
make worktree name=<topic> type=fix     # branch fix/<topic>
make worktree name=<name> type=spec     # branch spec/<name>
make worktree name=<topic> base=<branch> # stack on another branch instead of main
```

Claude Code's own `claude --worktree <name>` uses the same directory. Remove a finished worktree with `git worktree remove .claude/worktrees/<name>` after its PR is merged.

To compare against `main` without touching the working tree, export it: `git archive main | tar -x -C /tmp/<dir>`. Do not stash or check out in a worktree that has changes.

## Git

- Follow the git policy in `AGENTS.md`: branch, no commit or push without permission, never touch `main`.
- Stage files by name. Never stage `config.yaml`, `incoming/`, `.agents/` or anything containing a secret.
- No force push or amend after a push.
- Commit messages use a conventional prefix: `feat`, `fix`, `docs`, `test`, `chore`, `ci`, `spec`.

## Local notes and data handoff

- `incoming/` (gitignored): the user drops CSVs, PDFs, logs and photos here. Look there first.
- `.agents/` (gitignored): scratch notes such as PR triage and probe transcripts. Anything worth keeping moves into `docs/` or a spec.

## Spec, review and pull requests

See `docs/ways-of-working.md`. OpenSpec commands: `openspec list`, `openspec validate <name> --strict`, `openspec update` (after upgrading the CLI). Review records live in `.agents/reviews/<branch>/` (local); their summary goes into the PR description.

## CI/CD

- `ci.yml`: lint, map doc check and tests on every push and PR.
- `build.yml`: multi-arch Docker image, pushed for `main`, PRs and `v*` tags. Needs the `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` repository secrets.
- `release.yml`: a `v*` tag creates the GitHub release. See `.claude/skills/release/SKILL.md`.

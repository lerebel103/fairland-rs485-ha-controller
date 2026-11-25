---
name: release
description: Cut a new version of the Fairland RS485 HA controller (version-bump PR, tag, GitHub release). Use when the user asks to release or bump the version.
---

# Release

1. Ask the user for the version `X.Y.Z` and confirm `main` contains everything to ship.
2. Create a branch `release/vX.Y.Z` in a worktree (`make worktree name=vX.Y.Z type=release`). Never commit on `main`.
3. Update the version in exactly three files: `app/version.py` (`__version__`), `pyproject.toml`, and `uv.lock` (run `uv lock`).
4. Run `make check`. Commit `chore(release): vX.Y.Z` only with the user's permission, push the branch and open a PR.
5. After the user merges the PR, tag `main` with `vX.Y.Z` and push the tag (ask first). The tag triggers `.github/workflows/release.yml` (GitHub release with changelog) and `build.yml` (Docker image tagged with the version and `latest`).
6. Check both workflow runs succeeded and the release page lists the changes.

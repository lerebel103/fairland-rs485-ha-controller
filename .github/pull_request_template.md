## Summary

<!-- What this PR does and why, in two or three sentences. -->

## Spec

- OpenSpec change: `openspec/changes/<name>/` (or its `archive/` path)
- Requirements covered:
- Tasks completed:
- Spec changed in this PR: no / yes (what and why)

## Verification

- [ ] `make check` green locally
- [ ] Every acceptance criterion in scope has a test that fails without the change
- [ ] Docs updated where facts changed (`docs/modbus-map.md`, `docs/design-decisions.md`, `AGENTS.md`)

Not tested or deferred:

## Heat pump safety

- [ ] No change to the write allowlist, or the change is covered by an approved OpenSpec change
- [ ] No new path can write to the pump while the map is unverified
- [ ] Reads keep the vendor block shapes and request spacing

Touches code that can reach the pump: no / yes

## Review loop

<!-- From .agents/reviews/<branch>/summary.md: rounds run, reviewers used, findings fixed, findings declined and why. -->

## Reviewer focus

<!-- Where a second pair of eyes is most valuable. -->

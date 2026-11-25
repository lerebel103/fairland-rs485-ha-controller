# Review instructions for GitHub Copilot

This repository is a Docker service that bridges Fairland-built pool heat pumps (developed on a TiLAB AXCR21V) to Home Assistant: Modbus TCP to an RS485 gateway on one side, MQTT discovery on the other. It controls real hardware. The full rules are in `AGENTS.md` and `docs/ways-of-working.md`.

Every PR has already passed an agent review loop; its summary is in the PR description. Look for what that loop missed, and do not repeat findings the description lists as declined unless the stated reason is wrong.

## Flag as high priority

- Any Modbus write (function 05 or 06) that does not go through `app/modbus/codec.py` `encode`, or that targets a register outside `APP_WRITABLE_KEYS` in `app/modbus/registers.py`. The allowlist is: power, operating mode, power mode and the three setpoints.
- Any change to the allowlist or to `tests/unit/test_registers.py::test_app_write_allowlist_is_pinned` without a spec under `specs/` that calls for it.
- Reads that are not fixed blocks (48 for coils and discrete inputs, 3 for input and holding registers) from the first addresses listed in `docs/modbus-map.md`, or requests sent less than 60 ms apart or concurrently.
- A Home Assistant command that reaches state or the pump before its type, range and allowed values are validated.
- Retry loops without backoff, or a write replayed after a reconnect without re-reading state.
- Secrets or site-specific addresses committed anywhere except placeholders in `config.yaml.example`.

## Also check

- Each behaviour change traces to a requirement in the linked spec and has a test that would fail without it.
- Error paths are handled and tested: gateway unreachable, timeout, short or malformed reply, Modbus exception, MQTT disconnect.
- Tests were not weakened, skipped or deleted, and the coverage floor in `pyproject.toml` was not lowered.
- Temperature and scaling conversions use the codec, not inline arithmetic.
- `docs/modbus-map.md` tables are generated from code; hand edits inside the `GENERATED` markers are wrong.

## Conventions

Python 3.14, asyncio, ruff with a 120-column line. Prefer small pure functions and frozen dataclasses. Do not suggest new dependencies or broad refactors outside the PR's scope.

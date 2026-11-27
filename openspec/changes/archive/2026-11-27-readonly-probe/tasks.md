# Tasks

Implement in order. Each task is test-first: write the tests named, watch them fail, then write the code. Tick a task when its verify commands pass; every task also ends with `make check`. Requirement numbers refer to `specs/readonly-probe/spec.md` (scenario numbers, for example 5.5, are requirement.criterion) and to `design.md`.

Read only `design.md`, the delta spec, this file and the files listed in the design's "Files" section.

- [x] **1. Standard block starts in the register map**
  - Files: `app/modbus/registers.py`, `scripts/render_modbus_map.py`, `docs/modbus-map.md`, `tests/unit/test_registers.py`
  - Tests: `STANDARD_BLOCK_STARTS` equals the values in the design; every start is a multiple of the table's block size.
  - Code: add the constant; add the `read_blocks` generated block and markers; run `make modbus-map`.
  - Covers: 3.1, 3.2, Constraint 2
  - Verify: `uv run pytest tests/unit/test_registers.py tests/unit/test_modbus_map_doc.py -q`, `make check`

- [x] **2. Result types, fakes and the `ReadOnlyLink` happy path**
  - Files: `app/modbus/readonly_link.py`, `tests/unit/fakes.py`, `tests/unit/test_readonly_link.py`
  - Tests: an ok read of each table returns the values (bits as 0/1, cut to 48); the client method, address, count and device id are right for each table; `READ_METHODS` holds exactly the four read method names; two reads are at least 0.06 s apart by the fake clock and no sleep is requested when enough time has passed; a spec outside `allowed` raises `ValueError` and the client is not called; the hypothesis properties for method names and spacing.
  - Code: `Outcome`, `FailReason`, `BlockSpec`, `BlockResult`, `ReadClient`, `READ_METHODS`; `FakeClock`, `FakeClient`; `ReadOnlyLink.__init__`, `read_block` for the ok case, `close`.
  - Covers: 2.1, 2.3, 3.1, 3.2, 3.3, 3.4, 5.2, Constraint 3
  - Verify: `uv run pytest tests/unit/test_readonly_link.py -q`, `make check`

- [x] **3. `ReadOnlyLink` refusals and failures**
  - Files: `app/modbus/readonly_link.py`, `tests/unit/test_readonly_link.py`
  - Tests, one per case: exception 0x02 → refused with the code; exceptions 0x0A and 0x0B → failed, gateway exception; `ModbusIOException` → failed, no reply; another `ModbusException` → failed, no reply; too few bits and a wrong register count → failed, wrong length; `ConnectionException` → failed, connection lost; `client.connected` false before a request → connection lost without calling a read method; after connection lost, a further `read_block` calls nothing and returns connection lost; every failed outcome except connection lost is followed by `sleep(1.0)` and refused is not; no case calls the client twice for one block.
  - Code: the rest of `read_block`.
  - Covers: 3.6, 3.7, 5.3, 5.4, 5.6, Terms (block outcome)
  - Verify: `uv run pytest tests/unit/test_readonly_link.py -q`, `make check`

- [x] **4. `open_client`**
  - Files: `app/modbus/readonly_link.py`, `tests/unit/test_readonly_link.py`
  - Tests (replacing `AsyncModbusTcpClient` in the module with a fake class): the client is built with the host, `port`, `timeout`, `retries=0` and `reconnect_delay=0`; a successful connect returns the client; connect returning false, raising, and timing out each close the client and raise `ConnectionError`.
  - Code: `open_client`.
  - Covers: 1.4, 1.5, 3.5, 3.7
  - Verify: `uv run pytest tests/unit/test_readonly_link.py -q`, `make check`

- [x] **5. Block plan and `run_probe`**
  - Files: `app/modbus/probe.py`, `tests/unit/fakes.py`, `tests/unit/test_probe.py`
  - Tests (with `FakeLink`): standard plan order and contents; extended plan order and contents; without the extended flag no extended block is requested or present in the results; all ok → complete; one failed then ok → continues; two failed in a row → aborted, the rest not attempted, extended not read; failed, refused, failed → not aborted; connection lost → aborted on connection, the rest not attempted; connection lost that is also the second failure in a row → still aborted on connection; the failure count restarts at the first extended block; `should_stop` true before block n → interrupted, blocks from n not attempted; the hypothesis property that every planned block gets exactly one result in plan order.
  - Code: `EXTENDED_BLOCK_STARTS`, `RunEnd`, `ProbeRun`, `standard_plan`, `extended_plan`, `run_probe`, and `FakeLink`.
  - Covers: 3.2, 5.1, 5.3, 5.4, 5.5, 5.6, 6.1, 6.2, 6.3, 6.4, 9.3
  - Verify: `uv run pytest tests/unit/test_probe.py -q`, `make check`

- [x] **6. Report**
  - Files: `app/modbus/probe_report.py`, `tests/unit/test_probe_report.py`
  - Tests, building `ProbeRun` values by hand: section order and headings; a register line shows key, name, raw, decoded value, unit and notes; each block-line form (ok, refused, failed with each of the four reasons, gateway exception with its code, not attempted); value formats for bits, temperatures, tenths and power; an unmapped address shows raw only; an ok bit block shows the `raw bits` line with all 48 values in address order, including block 48; mode names and `unknown`; faults listed, `none`, and `unavailable`; each of the four suspect reasons and their precedence; summary shows the active setpoint per mode and all three when the mode is unknown or unavailable; estimated power present and `unavailable`; a refused, failed and not-attempted block each show `unavailable` for everything derived from them and never a zero; counts line and `run ended` line for each `RunEnd`; no extended section without the extended flag; extended section labelled unverified; ASCII lines in both renderings with `.`, `?` and `??` placeholders; input 30 and 31 labels.
  - Code: `render_report`.
  - Covers: 6.5, 7.1 to 7.11
  - Verify: `uv run pytest tests/unit/test_probe_report.py -q`, `make check`

- [x] **7. Transcript**
  - Files: `app/modbus/probe_report.py`, `tests/unit/test_probe_report.py`
  - Tests: the keys are exactly those in the schema; no host anywhere in the output; `started_utc` is UTC with a `Z` suffix; values null unless ok; reason and exception code populated correctly; an aborted and an interrupted run carry the right `run_end` and not-attempted blocks; extended blocks absent without the flag; the result is JSON-serialisable.
  - Code: `TRANSCRIPT_FORMAT_VERSION`, `build_transcript`.
  - Covers: 8.1, 8.2, 8.3
  - Verify: `uv run pytest tests/unit/test_probe_report.py -q`, `make check`

- [x] **8. CLI: arguments, pre-checks and prompt**
  - Files: `app/modbus/probe.py`, `tests/unit/test_probe.py`
  - Tests (injecting `stdin`, `stdout`, `stderr`, `open` and `install_interrupt`): `--help` raises `SystemExit(0)`, mentions the preconditions and exit statuses (via `capsys`) and opens nothing; a missing host raises `SystemExit(2)`; defaults; each invalid range returns 2 naming the argument on `stderr` and opens nothing; existing output path, missing directory and unwritable directory return 2 before any prompt, and `--overwrite` allows an existing path; non-interactive stdin without `--yes` returns 2 naming the flag; the prompt accepts exactly `yes` and rejects ` yes `, empty input, other text and end of input with 2 and no connection; an interrupt at the prompt returns 130 with no connection; `--yes` skips the prompt.
  - Code: argument parsing, steps 1–6 of the order of operations, `install_signal_handlers`, the interrupt state. Until task 9, the run step may raise `NotImplementedError`.
  - Covers: 1.1, 1.2, 1.3, 1.6, 4.1 to 4.5, 8.4, 9.1, 10.1, 10.2
  - Verify: `uv run pytest tests/unit/test_probe.py -q`, `uv run python -m app.modbus.probe --help`, `make check`

- [x] **9. CLI: run, transcript and exit status**
  - Files: `app/modbus/probe.py`, `tests/unit/test_probe.py`
  - Tests (with a `FakeClient` behind `open`): connection failure returns 2 naming host and port; an interrupt during the connection attempt returns 130; a clean run returns 0, prints the report and closes the client; `on_connected` is called once, after `open` returns and before the first request; a failed or refused standard block returns 1; a failed extended block alone still returns 0; a transcript is written with mode `x`, or `w` with `--overwrite`; an unwritable transcript still prints the report and returns 1; an interrupt mid-run (through `on_request`) returns 130, reports `run ended: interrupted`, writes the transcript and closes the client; an interrupt during the last block returns 130 and reports interrupted; no option changes which client methods are called; exactly one client is opened per run.
  - Code: `_run`, steps 7–10 of the order of operations, the `__main__` guard.
  - Covers: 1.4, 1.5, 2.2, 8.3, 8.5, 9.1, 9.2, 9.3
  - Verify: `uv run pytest tests/unit/test_probe.py -q`, `make check`

- [x] **10. Documentation**
  - Files: `README.md`, `.claude/skills/live-probe/SKILL.md`, `docs/design-decisions.md`
  - Change: add a "Verifying your heat pump" section to the README with one example from a checkout (`uv run python -m app.modbus.probe <host> --extended --output probe.json`) and one from the Docker image (`docker run --rm -it --network host lerebel103/fairland-rs485-ha-controller .venv/bin/python -m app.modbus.probe <host>`), and how to record results in `docs/modbus-map.md`. In the skill, make step 3 use the probe and allow its extended blocks, and replace step 5's rule with the outcomes in this spec. In `docs/design-decisions.md`, add under "Decided" that the project uses `pymodbus` with Modbus TCP framing and deliberately not RTU over TCP, taken from the spec's "Decisions and assumptions".
  - Covers: Constraint 5
  - Verify: `make check`

- [x] **11. Final check**
  - Run `make check`. The coverage floor in `pyproject.toml` must be unchanged and met.
  - Covers: Constraints 1 and 4
  - Verify: `make check`

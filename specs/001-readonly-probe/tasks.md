# Spec 001: Read-only probe — Tasks

Implement in order. Each task is test-first: write the tests named, watch them fail, then write the code. Tick a task when its verify commands pass; every task also ends with `make check`. Requirement numbers refer to `spec.md` Part 1; design sections to Part 2.

Read only `spec.md`, this file, and the files listed in the spec's "Files" section.

- [ ] **1. Standard block starts in the register map**
  - Files: `app/modbus/registers.py`, `scripts/render_modbus_map.py`, `docs/modbus-map.md`, `tests/unit/test_registers.py`
  - Tests: `STANDARD_BLOCK_STARTS` equals the values in the design; every start is a multiple of the table's block size.
  - Code: add the constant; add the `read_blocks` generated block and markers; run `make modbus-map`.
  - Covers: 3.1, 3.2, Constraint 2
  - Verify: `uv run pytest tests/unit/test_registers.py tests/unit/test_modbus_map_doc.py -q`, `make check`

- [ ] **2. Framing functions**
  - Files: `app/modbus/readonly_link.py`, `tests/unit/test_readonly_link.py`
  - Tests: `build_request` byte layout for each of the four tables; `ValueError` for function codes 5, 6, 15, 16 and a hypothesis property over all other codes; `parse_header`; `decode_bits` LSB-first; `decode_registers` big-endian; round-trip properties.
  - Code: types (`Outcome`, `FailReason`, `BlockSpec`, `BlockResult`, `ConnectionLost`, `ByteStream`, `Header`) and the pure functions.
  - Covers: 2.1, 2.3, 3.1
  - Verify: `uv run pytest tests/unit/test_readonly_link.py -q`, `make check`

- [ ] **3. Test fakes and the `ReadOnlyLink` happy path**
  - Files: `tests/unit/fakes.py`, `app/modbus/readonly_link.py`, `tests/unit/test_readonly_link.py`
  - Tests: an ok read of each table returns the decoded values; the request bytes use the right function code, start and count; transaction ids increment; two reads are at least 0.06 s apart by the fake clock and no sleep is requested when enough time has passed; a hypothesis property for the spacing.
  - Code: `FakeClock`, `FakeStream`; `ReadOnlyLink.__init__`, `read_block` steps 1–4 for the ok case, `close`.
  - Covers: 2.1, 3.3, 3.4, 5.2
  - Verify: `uv run pytest tests/unit/test_readonly_link.py -q`, `make check`

- [ ] **4. `ReadOnlyLink` refusals and failures**
  - Files: `app/modbus/readonly_link.py`, `tests/unit/test_readonly_link.py`
  - Tests, one per case: exception 0x02 → refused with the code; exceptions 0x0A and 0x0B → failed, gateway exception; timeout; malformed header (bad protocol id, bad length); mismatched unit id; mismatched function code; unknown transaction id; wrong byte count; connection lost on write, on header read and on body read; a late reply from an earlier transaction is discarded and the real reply is then accepted; connection lost during the quiet wait leaves that block's result unchanged and the next `read_block` writes nothing and returns connection lost; a spec outside `allowed` raises `ValueError` and nothing is written; with `READ_FUNCTION_CODE` monkeypatched to a write code, `read_block` raises `ValueError` and nothing is written; every failed outcome except connection lost is followed by `discard_for(1.0)` and refused is not; after connection lost, a further `read_block` writes nothing and returns connection lost; no case retries.
  - Code: the rest of `read_block`.
  - Covers: 2.3, 3.2, 3.5, 3.6, 3.7, 3.8, 5.3, 5.4, 5.6, Terms (block outcome), Constraint 3
  - Verify: `uv run pytest tests/unit/test_readonly_link.py -q`, `make check`

- [ ] **5. `TcpByteStream`**
  - Files: `app/modbus/readonly_link.py`, `tests/unit/test_readonly_link.py`
  - Tests (patching `asyncio.open_connection`): open succeeds; open timeout and refusal raise `OSError`; `read_exactly` maps incomplete read and connection errors to `ConnectionLost` and passes `TimeoutError` through; `write` maps errors; `discard_for` drops input and maps end of stream; `close` swallows `OSError`.
  - Covers: 1.4, 1.5
  - Verify: `uv run pytest tests/unit/test_readonly_link.py -q`, `make check`

- [ ] **6. Block plan and `run_probe`**
  - Files: `app/modbus/probe.py`, `tests/unit/fakes.py`, `tests/unit/test_probe.py`
  - Tests (with `FakeLink`): standard plan order and contents; extended plan order and contents; without the extended flag no extended block is requested or present in the results; all ok → complete; one failed then ok → continues; two failed in a row → aborted, the rest not attempted, extended not read; failed, refused, failed → not aborted; connection lost → aborted on connection, the rest not attempted; connection lost that is also the second failure in a row → still aborted on connection; the failure count restarts at the first extended block; `should_stop` true before block n → interrupted, blocks from n not attempted; the hypothesis property that every planned block gets exactly one result in plan order.
  - Code: `EXTENDED_BLOCK_STARTS`, `RunEnd`, `ProbeRun`, `standard_plan`, `extended_plan`, `run_probe`, and `FakeLink`.
  - Covers: 3.2, 5.1, 5.3, 5.4, 5.5, 5.6, 6.1, 6.2, 6.3, 6.4, 9.3
  - Verify: `uv run pytest tests/unit/test_probe.py -q`, `make check`

- [ ] **7. Report**
  - Files: `app/modbus/probe_report.py`, `tests/unit/test_probe_report.py`
  - Tests, building `ProbeRun` values by hand: section order and headings; a register line shows key, name, raw, decoded value, unit and notes; each block-line form (ok, refused, failed with each reason, gateway exception with its code, not attempted); value formats for bits, temperatures, tenths and power; an unmapped address shows raw only; mode names and `unknown`; faults listed, `none`, and `unavailable`; each of the four suspect reasons and their precedence; summary shows the active setpoint per mode and all three when the mode is unknown or unavailable; estimated power present and `unavailable`; a refused, failed and not-attempted block each show `unavailable` for everything derived from them and never a zero; counts line and `run ended` line for each `RunEnd`; no extended section without the extended flag; extended section labelled unverified; ASCII lines in both renderings with `.`, `?` and `??` placeholders; input 30 and 31 labels.
  - Code: `render_report`.
  - Covers: 6.5, 7.1 to 7.11
  - Verify: `uv run pytest tests/unit/test_probe_report.py -q`, `make check`

- [ ] **8. Transcript**
  - Files: `app/modbus/probe_report.py`, `tests/unit/test_probe_report.py`
  - Tests: the keys are exactly those in the schema; no host anywhere in the output; `started_utc` is UTC with a `Z` suffix; values null unless ok; reason and exception code populated correctly; an aborted and an interrupted run carry the right `run_end` and not-attempted blocks; extended blocks absent without the flag; the result is JSON-serialisable.
  - Code: `TRANSCRIPT_FORMAT_VERSION`, `build_transcript`.
  - Covers: 8.1, 8.2, 8.3
  - Verify: `uv run pytest tests/unit/test_probe_report.py -q`, `make check`

- [ ] **9. CLI: arguments, pre-checks and prompt**
  - Files: `app/modbus/probe.py`, `tests/unit/test_probe.py`
  - Tests (injecting `stdin`, `stdout`, `stderr`, `open_stream` and `install_interrupt`): `--help` raises `SystemExit(0)`, mentions the preconditions and exit statuses (via `capsys`) and opens nothing; a missing host raises `SystemExit(2)`; defaults; each invalid range returns 2 naming the argument on `stderr` and opens nothing; existing output path, missing directory and unwritable directory return 2 before any prompt, and `--overwrite` allows an existing path; non-interactive stdin without `--yes` returns 2 naming the flag; the prompt accepts exactly `yes` and rejects ` yes `, empty input, other text and end of input with 2 and no connection; an interrupt at the prompt returns 130 with no connection; `--yes` skips the prompt.
  - Code: argument parsing, steps 1–6 of the order of operations, `install_signal_handlers`, the interrupt state. Until task 10, the run step may raise `NotImplementedError`.
  - Covers: 1.1, 1.2, 1.3, 1.6, 4.1 to 4.5, 8.4, 9.1, 10.1, 10.2
  - Verify: `uv run pytest tests/unit/test_probe.py -q`, `uv run python -m app.modbus.probe --help`, `make check`

- [ ] **10. CLI: run, transcript and exit status**
  - Files: `app/modbus/probe.py`, `tests/unit/test_probe.py`
  - Tests (with a `FakeStream` behind `open_stream`): connection failure returns 2 naming host and port; an interrupt during the connection attempt returns 130; a clean run returns 0, prints the report and closes the stream; a failed or refused standard block returns 1; a failed extended block alone still returns 0; a transcript is written with mode `x`, or `w` with `--overwrite`; an unwritable transcript still prints the report and returns 1; an interrupt mid-run (through `on_request`) returns 130, reports `run ended: interrupted`, writes the transcript and closes the stream; an interrupt during the last block returns 130 and reports interrupted; no option changes the function codes sent; exactly one stream is opened per run.
  - Code: `_run`, steps 7–10 of the order of operations, the `__main__` guard.
  - Covers: 1.4, 1.5, 2.2, 8.3, 8.5, 9.1, 9.2, 9.3
  - Verify: `uv run pytest tests/unit/test_probe.py -q`, `make check`

- [ ] **11. Documentation**
  - Files: `README.md`, `.claude/skills/live-probe/SKILL.md`, `docs/design-decisions.md`
  - Change: add a "Verifying your heat pump" section to the README with one example from a checkout (`uv run python -m app.modbus.probe <host> --extended --output probe.json`) and one from the Docker image (`docker run --rm -it --network host lerebel103/fairland-rs485-ha-controller .venv/bin/python -m app.modbus.probe <host>`), and how to record results in `docs/modbus-map.md`. In the skill, make step 3 use the probe and allow its extended blocks, and replace step 5's rule with the outcomes in this spec. In `docs/design-decisions.md`, add under "Decided" the entry on the probe not using `pymodbus`, taken from the spec's "Open questions and assumptions".
  - Covers: Constraint 5
  - Verify: `make check`

- [ ] **12. Final check**
  - Run `make check`. The coverage floor in `pyproject.toml` must be unchanged and met.
  - Covers: Constraints 1 and 4
  - Verify: `make check`

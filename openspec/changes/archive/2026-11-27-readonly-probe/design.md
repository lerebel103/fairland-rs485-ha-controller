## Context

### Terms (normative)

- **Standard block**: a read of the vendor's fixed count starting at a first address the vendor table labels as allowed. The complete list is: coils 0; discrete inputs 0 and 48; holding registers 0, 3, 6, 9, 12, 15, 18; input registers 0, 3, 6, 9, 12.
- **Extended block**: a read of the vendor's fixed count starting at one of the addresses in this list, which is the complete and normative definition: holding register 24; input registers 15, 18, 21, 24, 27, 30. These are the blocks that `docs/modbus-map.md` asks the probe to settle, and no others. Holding block 21 is excluded: its only basis is an older table revision's expansion-valve settings, which the map deliberately leaves out. Input block 30 covers addresses 30 to 32, and no source documents address 32.
- **Block outcome**: exactly one of the following.
  - **ok**: a valid reply with the expected number of values.
  - **refused**: a valid Modbus exception response other than codes 0x0A and 0x0B. The pump answered and declined.
  - **failed**: no usable answer from the pump. The reasons are: no reply (no valid reply within the timeout; this includes silence and any frame the Modbus library discards as malformed or as not matching the request); gateway exception (code 0x0A, gateway path unavailable, or 0x0B, target device failed to respond, which the gateway generates when the pump is silent); wrong number of values; connection lost.
  - **not attempted**: the run ended before the block was read.

  When the extended flag is absent, extended blocks are not part of the run: they have no outcome and appear in neither the report, the counts nor the transcript.
- **Interrupt**: SIGINT (Ctrl-C) or SIGTERM (as sent by `docker stop`). Both are treated the same.


## Constraints

These bind the design and the tasks. They are not acceptance criteria.

1. **Testable without hardware.** Every acceptance criterion above must be provable by an automated test against a substitute for the Modbus connection. No test opens a network connection, and the request spacing and the post-timeout wait must be testable without real delays.
2. **Single source for the map.** Block sizes, register definitions, decoding and fault decoding come from `app/modbus/registers.py`, `codec.py` and `faults.py`. The probe does not restate them; the labels for input registers 21 to 31, which are not in the map, are the probe's own and are marked unverified. The list of standard first addresses is added to `registers.py`, covered by the map doc check, so that spec 002's client uses the same list. The extended list belongs to the probe alone.
3. **One request sender, under `app/modbus/`, on `pymodbus`.** All probe requests pass through one object built on the project's pinned `pymodbus`, which is where Requirement 2.3 is enforced. It and the rest of the probe live under `app/modbus/`, so that the safety review triggers on any change to them and `AGENTS.md`'s rule that only `app/modbus/` builds Modbus requests holds. Spec 002 decides whether its client reuses this sender.
4. **Coverage.** The probe is included in the coverage measurement and the project's coverage floor stays satisfied.
5. **Documentation.**
   - Amended on this branch at this gate, following the maintainer's agreement to the exception:
     - `AGENTS.md` safety rule 3 and bus rule 1 in `docs/modbus-map.md`: name the probe's opt-in extended reads as the one exception.
     - `docs/design-decisions.md`: record the exception under "Decided".
     - `.github/copilot-instructions.md`, `.claude/agents/safety-reviewer.md` and `docs/ways-of-working.md`: the same exception, so that no reviewer flags the approved reads.
   - Delivered with the code:
     - `README.md`: an example command from a checkout and from the Docker image.
     - `.claude/skills/live-probe/SKILL.md`: use the probe; in step 3 allow the extended blocks; in step 5 replace "stop on exception codes" with the outcomes defined here (a refused block is an answer, two failed blocks in a row end the run).
   - After the first live run, by the maintainer and not as a task: fill in the verification table in `docs/modbus-map.md`, and move the open question about holding register 25 and input registers 15–31 in `docs/design-decisions.md` to "Decided".


## Design


### Overview

The probe uses the project's pinned `pymodbus` (3.16.1) with its asynchronous Modbus TCP client and standard Modbus TCP framing. The gateway is configured as a Modbus TCP to RTU bridge. A thin wrapper, `ReadOnlyLink`, is the only code that touches the client; it exposes one operation, reading a block, and adds the vendor's spacing and the outcome classification.

```
python -m app.modbus.probe
  cli (main)            arguments, pre-checks, prompt, signals, exit status
   └─ run_probe         block order, abort rules, extended rules
       └─ ReadOnlyLink  one request at a time, spacing, quiet wait, outcomes
           └─ pymodbus AsyncModbusTcpClient (a fake client in tests)
  render_report / build_transcript   pure functions over the ProbeRun
```

## Files

| Path | Action | Content |
|---|---|---|
| `app/modbus/registers.py` | modify | Add `STANDARD_BLOCK_STARTS` |
| `scripts/render_modbus_map.py` | modify | Render a `read_blocks` generated block |
| `docs/modbus-map.md` | modify | Replace the hand-written table under bus rule 1 with the `read_blocks` generated block |
| `app/modbus/readonly_link.py` | create | Result types, `ReadClient`, `open_client`, `ReadOnlyLink` |
| `app/modbus/probe.py` | create | Block plan, `run_probe`, CLI `main`, `__main__` guard |
| `app/modbus/probe_report.py` | create | `render_report`, `build_transcript` |
| `tests/unit/fakes.py` | create | `FakeClient`, `FakeClock`, `FakeLink` |
| `tests/unit/test_registers.py` | modify | Tests for `STANDARD_BLOCK_STARTS` |
| `tests/unit/test_readonly_link.py` | create | Link and `open_client` tests |
| `tests/unit/test_probe.py` | create | `run_probe` and CLI tests |
| `tests/unit/test_probe_report.py` | create | Report and transcript tests |
| `README.md` | modify | "Verifying your heat pump" section with example commands |
| `.claude/skills/live-probe/SKILL.md` | modify | Steps 3 and 5, per Constraint 5 |

Files the implementer may read: the above, plus `app/modbus/codec.py`, `app/modbus/faults.py`, `app/version.py`, `tests/unit/test_modbus_map_doc.py`, `pyproject.toml`, `docs/design-decisions.md` and `Makefile`. Nothing else is needed.

## `app/modbus/registers.py`

Add after `READ_BLOCK_SIZE`:

```python
# First addresses the vendor table labels as allowed for a read (bus rule 1).
STANDARD_BLOCK_STARTS: dict[Table, tuple[int, ...]] = {
    Table.COIL: (0,),
    Table.DISCRETE_INPUT: (0, 48),
    Table.HOLDING: (0, 3, 6, 9, 12, 15, 18),
    Table.INPUT: (0, 3, 6, 9, 12),
}
```

`scripts/render_modbus_map.py` gains `render_read_blocks()` returning a table with columns `Table | Read function | Count | Allowed first addresses (vendor)`, one row per `Table` in the order coil, discrete_input, holding, input, and `blocks()` adds it under the name `read_blocks`. Cell formats: the table's enum value (`coil`, `discrete_input`, `holding`, `input`); the read function code as two decimal digits (`01`); the count as an integer; the addresses joined with `, `.

In `docs/modbus-map.md`, delete the indented table inside bus rule 1 and end that rule with the sentence "The allowed shapes are in the table below the rules." Put the `<!-- BEGIN GENERATED: read_blocks -->` / `<!-- END GENERATED: read_blocks -->` markers at column 0 on their own lines directly after rule 3, then run `make modbus-map`.

## `app/modbus/readonly_link.py`

### Types

```python
class Outcome(StrEnum):
    OK = "ok"
    REFUSED = "refused"
    FAILED = "failed"
    NOT_ATTEMPTED = "not_attempted"

class FailReason(StrEnum):
    NO_REPLY = "no_reply"
    GATEWAY_EXCEPTION = "gateway_exception"
    WRONG_LENGTH = "wrong_length"
    CONNECTION_LOST = "connection_lost"

@dataclass(frozen=True, slots=True)
class BlockSpec:
    table: Table
    start: int
    extended: bool = False

    @property
    def count(self) -> int: ...          # READ_BLOCK_SIZE[self.table]

@dataclass(frozen=True, slots=True)
class BlockResult:
    spec: BlockSpec
    outcome: Outcome
    values: tuple[int, ...] | None = None    # bits as 0/1; set only when outcome is OK
    reason: FailReason | None = None         # set only when outcome is FAILED
    exception_code: int | None = None        # set for REFUSED and for GATEWAY_EXCEPTION

class ReadClient(Protocol):
    """The part of pymodbus' AsyncModbusTcpClient that the link uses."""
    @property
    def connected(self) -> bool: ...
    async def read_coils(self, address: int, *, count: int, device_id: int) -> Any: ...
    async def read_discrete_inputs(self, address: int, *, count: int, device_id: int) -> Any: ...
    async def read_holding_registers(self, address: int, *, count: int, device_id: int) -> Any: ...
    async def read_input_registers(self, address: int, *, count: int, device_id: int) -> Any: ...
    def close(self) -> None: ...
```

### pymodbus facts this design relies on (3.16.1)

- `AsyncModbusTcpClient(host, *, port, timeout, retries, reconnect_delay)`; the default framer is Modbus TCP (`FramerType.SOCKET`). `await client.connect()` returns a bool. `client.close()` is synchronous. `client.connected` is a bool property.
- The four read methods are awaited and take `address` positionally and `count` and `device_id` as keywords.
- A reply object has `isError()`. An error reply has `exception_code`. A bit reply has `bits` (a list of bools, padded to a multiple of 8). A register reply has `registers` (a list of ints).
- No valid reply within the timeout raises `pymodbus.exceptions.ModbusIOException`. A lost or closed connection raises `pymodbus.exceptions.ConnectionException`. Both derive from `ModbusException`.
- The library matches replies to requests by transaction id and drops frames that do not match.

### `open_client`

```python
READ_METHODS: dict[Table, str] = {
    Table.COIL: "read_coils",
    Table.DISCRETE_INPUT: "read_discrete_inputs",
    Table.HOLDING: "read_holding_registers",
    Table.INPUT: "read_input_registers",
}
GATEWAY_EXCEPTION_CODES: frozenset[int] = frozenset({0x0A, 0x0B})

async def open_client(host: str, port: int, timeout: float) -> ReadClient
```

Creates `AsyncModbusTcpClient(host, port=port, timeout=timeout, retries=0, reconnect_delay=0)`. `retries=0` and `reconnect_delay=0` switch off the library's automatic retries and reconnection (Requirement 3.7). Awaits `asyncio.wait_for(client.connect(), timeout)`. If that returns false, times out or raises, it calls `client.close()` and raises `ConnectionError`. Tests replace `AsyncModbusTcpClient` in this module with a fake class; no socket is opened.

### `ReadOnlyLink`

```python
MIN_GAP_S = MIN_REQUEST_GAP_S          # 0.06, from registers.py
QUIET_AFTER_FAILURE_S = 1.0

class ReadOnlyLink:
    def __init__(self, client: ReadClient, *, unit_id: int,
                 allowed: frozenset[BlockSpec],
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
                 monotonic: Callable[[], float] = time.monotonic) -> None
    async def read_block(self, spec: BlockSpec) -> BlockResult
    def close(self) -> None
    @property
    def connection_lost(self) -> bool
```

`read_block` is the link's only request operation, and `READ_METHODS` is the only way it reaches the client, so no write can be issued through it (Requirement 2.3). It never raises for bus conditions; it always returns a `BlockResult`. It raises `ValueError`, before calling the client, when `spec` is not in `allowed` (Requirement 3.2 by construction). Algorithm:

1. If `spec not in allowed`, raise `ValueError`.
2. If `connection_lost` is already true, or `client.connected` is false, set `connection_lost` and return `FAILED / CONNECTION_LOST` without calling a read method.
3. If a previous request ended less than `MIN_GAP_S` ago by `monotonic()`, `await sleep(remaining)`.
4. `reply = await getattr(client, READ_METHODS[spec.table])(spec.start, count=spec.count, device_id=unit_id)`.
   - `ConnectionException` → set `connection_lost`, result `FAILED / CONNECTION_LOST`.
   - `ModbusIOException`, or any other `ModbusException` → `FAILED / NO_REPLY`. Catch `ConnectionException` first.
   - Any `OSError` → set `connection_lost`, result `FAILED / CONNECTION_LOST`.
   - `reply.isError()`: `exception_code` in `GATEWAY_EXCEPTION_CODES` → `FAILED / GATEWAY_EXCEPTION` with the code; any other code → `REFUSED` with the code.
   - Bit tables: if `len(reply.bits) < spec.count` → `FAILED / WRONG_LENGTH`; otherwise the values are the first `spec.count` bits as 0/1.
   - Register tables: if `len(reply.registers) != spec.count` → `FAILED / WRONG_LENGTH`; otherwise the values are the registers.
5. Record the end time with `monotonic()`.
6. If the outcome is `FAILED` with a reason other than `CONNECTION_LOST`, `await sleep(QUIET_AFTER_FAILURE_S)` before returning (Requirement 3.6).

`read_block` is awaited sequentially by `run_probe`, which gives Requirement 3.3; step 3 gives Requirement 3.4. `close` calls `client.close()`.

## `app/modbus/probe.py`

```python
EXTENDED_BLOCK_STARTS: dict[Table, tuple[int, ...]] = {
    Table.HOLDING: (24,),
    Table.INPUT: (15, 18, 21, 24, 27, 30),
}
MAX_CONSECUTIVE_FAILURES = 2

class RunEnd(StrEnum):
    COMPLETE = "complete"
    ABORTED_FAILURES = "aborted_consecutive_failures"
    ABORTED_CONNECTION = "aborted_connection_lost"
    INTERRUPTED = "interrupted"

@dataclass(frozen=True, slots=True)
class ProbeRun:
    results: tuple[BlockResult, ...]     # one per block in the run, in plan order
    extended: bool
    end: RunEnd
    started_utc: datetime

def standard_plan() -> tuple[BlockSpec, ...]    # coil, discrete_input, holding, input; ascending
def extended_plan() -> tuple[BlockSpec, ...]    # holding, input; ascending; extended=True

class BlockReader(Protocol):
    async def read_block(self, spec: BlockSpec) -> BlockResult: ...

async def run_probe(link: BlockReader, *, extended: bool,
                    should_stop: Callable[[], bool] = lambda: False,
                    now: Callable[[], datetime] = lambda: datetime.now(UTC)) -> ProbeRun
```

`run_probe` rules:

- The run's blocks are `standard_plan()`, plus `extended_plan()` when `extended` is true. Every block in the run gets exactly one `BlockResult`.
- Before each block, if `should_stop()` is true: mark this and all later blocks `NOT_ATTEMPTED`, end `INTERRUPTED`.
- After each block, apply these checks in this order.
- First: if the result's reason is `CONNECTION_LOST`, mark all later blocks `NOT_ATTEMPTED` and end `ABORTED_CONNECTION`, even when it is also the second failure in a row.
- Then: a `FAILED` result increments the consecutive-failure count; `OK` or `REFUSED` resets it to 0.
- If the count reaches `MAX_CONSECUTIVE_FAILURES`: mark all later blocks `NOT_ATTEMPTED` (standard and extended), end `ABORTED_FAILURES`.
- The count is reset to 0 before the first extended block.
- Otherwise end `COMPLETE`.

### CLI

```
python -m app.modbus.probe HOST [--port 4196] [--unit-id 1] [--timeout 3.0]
                                [--extended] [--yes] [--output PATH] [--overwrite]
```

```python
InstallInterrupt = Callable[[Callable[[], None]], None]

def main(argv: Sequence[str] | None = None, *,
         stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout, stderr: TextIO = sys.stderr,
         open: Callable[[str, int, float], Awaitable[ReadClient]] = open_client,
         install_interrupt: InstallInterrupt = install_signal_handlers) -> int

def install_signal_handlers(on_interrupt: Callable[[], None]) -> None
async def _run(args: argparse.Namespace, open, should_stop: Callable[[], bool],
               on_connected: Callable[[], None]) -> ProbeRun
```

The module ends with `if __name__ == "__main__": raise SystemExit(main())`.

Streams: the preconditions, the prompt and the report go to `stdout`; every error message goes to `stderr`. The one exception is argparse: `--help` and usage errors are written by argparse to `sys.stdout`/`sys.stderr` and leave `main` as `SystemExit` (0 for help, 2 for a usage error). Tests for those use `pytest.raises(SystemExit)` and `capsys`.

### Interrupt handling

`main` owns one piece of state: `interrupted: bool` and `phase`, one of `"waiting"` or `"running"`.

- `install_signal_handlers` registers one handler for `SIGINT` and `SIGTERM` with `signal.signal`; the handler calls `on_interrupt()`.
- `on_interrupt` sets `interrupted = True`. If `phase` is `"waiting"` it then raises `KeyboardInterrupt`; if `"running"` it returns, and the run stops at the next block boundary through `should_stop`.
- `phase` is `"waiting"` from installation until the client is connected, covering the prompt and the connection attempt, and `"running"` from then until `run_probe` returns. The state belongs to `main`; `_run` cannot assign it, so `main` passes `on_connected`, a callback that sets `phase = "running"`, and `_run` calls it as soon as `open` returns.
- `main` catches `KeyboardInterrupt` around the prompt and around `asyncio.run` and returns 130.
- After `run_probe` returns, if `interrupted` is true `main` replaces the run's end with `dataclasses.replace(run, end=RunEnd.INTERRUPTED)`, whatever `run_probe` decided. So an interrupt during the last block, or during a block that also triggers an abort, is reported and exits as interrupted.
- An interrupt while a block is in flight lets that block finish (at most one timeout), then stops.
- `ReadOnlyLink` also takes the stop predicate. After the spacing wait, immediately before sending, it checks the predicate and, if it is true, returns the block as `NOT_ATTEMPTED` without sending. So an interrupt during the 60 ms spacing never leads to a new request.
- An interrupt that arrives while the report is printed or the transcript is produced still makes the exit status 130. The transcript is built from the run end current at that moment and is written again if the interrupt flag changed while it was being written, so the saved `run_end` agrees with the exit status. The report already printed to stdout is not reprinted.

Tests never send a real signal. They pass their own `install_interrupt`, keep the callback it receives, and call it at the chosen moment: from a fake `stdin.readline` for the prompt, from a fake `open` for the connection attempt, and from `FakeClient`'s `on_request` hook during a run.

### Order of operations

Each step returns the stated status on failure.

1. Parse arguments with `argparse`. The epilog lists the three preconditions and the four exit statuses.
2. Validate ranges: port 1–65535, unit id 1–247, timeout 0.5–30. → 2, message names the argument.
3. If `--output` is given: the path must not be a directory, and must not exist unless `--overwrite`; its parent directory must exist and be writable (`os.access(parent, os.W_OK)`). → 2.
4. If `--yes` is absent and `stdin.isatty()` is false → 2, message names `--yes`.
5. Call `install_interrupt(on_interrupt)`.
6. If `--yes` is absent: print the preconditions and a prompt, read one line with `stdin.readline()`; proceed only if `line.rstrip("\r\n") == "yes"`. Anything else, including end of input (an empty string) → 2.
7. `asyncio.run(_run(...))`. `_run` awaits `open(host, port, timeout)` (an `OSError`, which includes `ConnectionError`, propagates to `main`, which prints a message naming host and port and returns 2), calls `on_connected()`, builds a `ReadOnlyLink` with `allowed` set to the run's plan, awaits `run_probe`, and closes the client in a `finally` that starts as soon as `open` returns, so an interrupt right after connecting still closes it. `ReadOnlyLink` also treats a raw `OSError` from a read as connection lost.
8. Apply the interrupt replacement described above, then print `render_report(run)`.
9. If `--output` is given, write `json.dumps(build_transcript(...), indent=2)`, opening the file with mode `"x"`, or `"w"` when `--overwrite` is set. On `OSError` print the error and remember the failure.
10. Exit status: 130 if `interrupted`; else 1 if any standard block's outcome is not `OK` or the transcript write failed; else 0.

## `app/modbus/probe_report.py`

```python
TRANSCRIPT_FORMAT_VERSION = 1

def render_report(run: ProbeRun) -> str
def build_transcript(run: ProbeRun, *, port: int, unit_id: int, timeout_s: float, probe_version: str) -> dict[str, Any]
```

Both are pure. `probe_version` is `app.version.__version__`.

### Report layout

Plain text, sections in this order, each starting with the heading shown. This example is a run with the extended flag in which holding block 15 was refused and input block 9 got no reply.

```
== Summary: compare with the pump display ==
power (coil 0)               raw 1    on
running (discrete input 0)   raw 1    on
operating_mode               raw 1    heating
power_mode                   raw 1    silence
target_temp_heating          raw 112  26.0 °C
inlet_temp                   raw 108  24.0 °C
outlet_temp                  raw 112  26.0 °C
ambient_temp                 raw 96   18.0 °C
estimated compressor power   unavailable

== Active faults ==
E3  protection  No water flow

== Standard blocks ==
[ok] holding 0-2
  0  operating_mode    Function selection            raw 1    heating  (0 auto, 1 heating, 2 cooling.)
  1  power_mode        Working mode selection        raw 1    silence  (0 smart, 1 silence, 2 super silence (community), 3 turbo (not on all models).)
  2  target_temp_auto  Auto mode target temperature  raw 112  26.0 °C
[refused: exception 0x02] holding 15-17
[failed: no reply] input 9-11

== Extended blocks (outside the vendor's allowed first addresses; unverified) ==
[ok] input 21-23
  21  -  raw 86
  22  -  raw 49
  23  -  raw 46
board version (unverified)   low byte: "V1.02"  two bytes: ".V.1...0.2"
model code (unverified)      low byte: "AC21"   two bytes: ".A.C.2.1"
supply voltage (unverified)  raw 238
compressor restart delay s (unverified)  raw 0

== Result ==
standard: 13 ok, 1 refused, 1 failed, 0 not attempted
extended: 7 ok, 0 refused, 0 failed, 0 not attempted
run ended: complete
```

Column alignment is cosmetic and not tested; tests assert on the content of lines, with runs of spaces collapsed.

Rules:

- **Block line:** `[ok] <table> <start>-<end>`; `[refused: exception 0xNN]`; `[failed: <reason>]` where reason is the `FailReason` value with underscores as spaces, followed by ` (exception 0xNN)` for a gateway exception; `[not attempted]`. Exception codes are two upper-case hex digits.
- **Register line** under an ok block, one per address: the address; the register key, or `-` when the map has no entry; the register's name; `raw <value>`; the decoded value with unit; the register's notes in parentheses when it has any. An address with no map entry shows the address, `-` and the raw value only.
- **Bit blocks:** the first line under an ok bit block is `raw bits: ` followed by all 48 values as `0`/`1` in address order, in groups of 8 separated by a space, so every address's raw value is shown (Requirement 7.1). Then one register line per address that has a map entry, then one line `other bits set: <addresses joined with ", ">` or `other bits set: none`. Discrete input block 48 shows the `raw bits` line and `see Active faults`, with no register lines.
- **Value formats:** a bit is `on` or `off`. A temperature has one decimal place and ` °C`. A `raw / 10` value has one decimal place and its unit. A raw value with a unit is the integer and the unit. Estimated power is rounded to a whole number of W, followed by ` (estimated: current x PFC voltage)`.
- **Mode names** come from `OperatingMode` and `PowerMode`, lower-cased with underscores as spaces; an undefined value shows `unknown`.
- **Suspect:** append ` SUSPECT (<why>)`. When several reasons apply, show the first in this order: `0 means unsupported`, `outside raw range`, `off raw step`, `implausible temperature`. Range and step checks apply only where the register defines `raw_min` and `raw_max`.
- **Unavailable:** anything derived from a block that is not ok shows `unavailable`. That covers summary items, the power estimate (unless both inputs were read) and the faults section (unless discrete input block 48 is ok; when it is ok with no bit set the section shows `none`).
- **Summary setpoint:** the active one for a known operating mode (`target_temp_auto`, `target_temp_heating`, `target_temp_cooling` for 0, 1, 2), or all three when the mode is unknown or unavailable.
- **Extended section:** it, its counts line and the lines below its blocks appear only when `run.extended` is true.
- **ASCII lines:** board version is input registers 21–25 and model code is 26–29. The low-byte rendering has one character per register; the two-byte rendering has two (high byte, then low byte). A byte outside 0x20–0x7E is `.`. A register from a block that is not ok is `?` in the low-byte rendering and `??` in the two-byte rendering.
- **Input registers 30 and 31:** labelled as in the example, with `raw <value>` or `unavailable`.
- **Counts line:** the words `ok`, `refused`, `failed`, `not attempted`. **Run ended:** `complete`, `aborted after consecutive failures`, `aborted on connection loss` or `interrupted`.

### Transcript schema

```json
{
  "format_version": 1,
  "probe_version": "0.0.1",
  "started_utc": "2026-11-26T03:15:00Z",
  "port": 4196,
  "unit_id": 1,
  "timeout_s": 3.0,
  "extended": true,
  "run_end": "complete",
  "blocks": [
    {"table": "holding", "start": 0, "count": 3, "extended": false,
     "outcome": "ok", "reason": null, "exception_code": null, "values": [1, 1, 112]}
  ]
}
```

`run_end` takes the `RunEnd` values, `outcome` the `Outcome` values, `reason` the `FailReason` values. `values` is null unless the outcome is ok. No other keys are written.

## Decisions and assumptions

- **`pymodbus` with Modbus TCP framing.** The maintainer decided the probe uses the pinned `pymodbus` and proper Modbus TCP framing. The gateway can also carry RTU over TCP; that mode is deliberately not used. The gateway's Modbus TCP to RTU behaviour is well understood and it is configured to follow the Modbus TCP specification, so matching replies to requests is left to the library's transaction ids. Task 10 records this in `docs/design-decisions.md`.
- **Gateway exception codes.** Whether the gateway returns 0x0B or stays silent when the pump does not answer depends on its settings. Both are handled as failed.
- **Library behaviour after a missing reply.** Whether `pymodbus` keeps the connection open after a `ModbusIOException` with `retries=0` is not relied on: step 2 of `read_block` checks `client.connected` before every request and reports a closed connection as connection lost.

## Test strategy

- `tests/unit/fakes.py`:
  - `FakeClock`: `monotonic()` returns a float; `async sleep(s)` advances it and records the call.
  - `FakeClient(clock, on_request=None)`: implements `ReadClient`. Scripted with one action per expected request: `bits([...])`, `registers([...])`, `error(code)`, `no_reply()` (raises `ModbusIOException`), `lost()` (raises `ConnectionException` and sets `connected` false). Records every call as (method name, address, count, device_id, clock time). `on_request(index)` is called at the start of the request with that zero-based index, which is how tests trigger an interrupt mid-run. Any attribute other than the `ReadClient` members raises `AssertionError`, so a test fails if the link reaches for a write method.
  - `FakeLink`: a `BlockReader` returning scripted `BlockResult`s and recording the specs it was asked for.
- No test opens a socket. `open_client` is tested by replacing `AsyncModbusTcpClient` in `app.modbus.readonly_link` with a fake class.
- Timing is asserted from the recorded clock times, never with real sleeps.
- Properties (hypothesis):
  - For any sequence of scripted client actions, the link calls only methods named in `READ_METHODS`, with the count from `READ_BLOCK_SIZE`.
  - For any sequence of scripted outcomes, `run_probe` returns exactly one result per planned block, in plan order, and never asks the link for a block not in the plan.
  - For any sequence of scripted client actions, every recorded request starts at least 0.06 s after the previous one ended, and at least 1 s after a failed one.

## Verification commands

```
uv run pytest tests/unit/test_registers.py tests/unit/test_modbus_map_doc.py -q
uv run pytest tests/unit/test_readonly_link.py -q
uv run pytest tests/unit/test_probe.py -q
uv run pytest tests/unit/test_probe_report.py -q
uv run python -m app.modbus.probe --help
make check
```

`make check` must pass with the coverage floor unchanged. No command in this spec connects to a heat pump or gateway; the first live run is done by the maintainer under the `live-probe` skill after the code is merged.

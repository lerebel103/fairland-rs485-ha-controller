# Spec 001: Read-only probe

Part 1 is the requirements. Part 2 is the design an implementer builds from. `tasks.md` is the work order.

# Part 1: Requirements

## Introduction

The register map in `docs/modbus-map.md` comes from Fairland's protocol table and from community projects on other models. It has never been checked against the reference unit, a TiLAB TurboSilence AXCR21V. Every later spec depends on that map being right, and the project's safety rules forbid any write to the pump until it is verified.

This spec delivers a command-line probe that connects to the pump through the RS485 gateway, reads the map once using only the vendor's read shapes, and reports the raw and decoded values so the maintainer can compare them with the pump's display and fill in the verification table.

The probe never writes to the pump. It is a one-shot diagnostic tool, not part of the running controller.

### In scope

- One-shot, read-only reads of every block in the map over Modbus TCP.
- A human-readable report and a machine-readable transcript.
- Opt-in reads of blocks the vendor does not label as allowed first addresses.

### Out of scope

- Any Modbus write.
- Continuous polling, MQTT, Home Assistant, and `config.yaml`.
- Automatically editing `docs/modbus-map.md`. The maintainer records the results.
- Auto-detecting serial settings or scanning for unit ids.

### Deviation from bus rule 1

`AGENTS.md` safety rule 3 and bus rule 1 in `docs/modbus-map.md` say a read must start on a first address the vendor labels as allowed. The extended blocks in this spec do not. This is a deliberate, narrow exception:

- It applies to the probe only, never to the controller.
- It is opt-in per run, read-only, and uses the vendor's fixed counts.
- It covers exactly the blocks `docs/modbus-map.md` asks the probe to settle: holding register 25 (block 24) and input registers 15–20 "need the probe to settle them", and of input registers 21–31 it says "the probe should read them". `docs/design-decisions.md` lists the same point as an open question.

The maintainer agreed this exception explicitly on 2026-11-26, separately from approval of this document. The rule wording in `AGENTS.md`, `docs/modbus-map.md` and the documents that restate it was amended on this branch at the same time (see Constraint 5), so the binding documents and the spec agree.

The vendor's stated risk for an unlabelled read is that it "may return incorrect data". The report therefore labels every extended value as unverified.

### Terms

- **Standard block**: a read of the vendor's fixed count starting at a first address the vendor table labels as allowed. The complete list is: coils 0; discrete inputs 0 and 48; holding registers 0, 3, 6, 9, 12, 15, 18; input registers 0, 3, 6, 9, 12.
- **Extended block**: a read of the vendor's fixed count starting at one of the addresses in this list, which is the complete and normative definition: holding register 24; input registers 15, 18, 21, 24, 27, 30. These are the blocks that `docs/modbus-map.md` asks the probe to settle, and no others. Holding block 21 is excluded: its only basis is an older table revision's expansion-valve settings, which the map deliberately leaves out. Input block 30 covers addresses 30 to 32, and no source documents address 32.
- **Block outcome**: exactly one of the following.
  - **ok**: a valid reply with the expected number of values.
  - **refused**: a valid Modbus exception response other than codes 0x0A and 0x0B. The pump answered and declined.
  - **failed**: no usable answer from the pump. The reasons are: timeout; gateway exception (code 0x0A, gateway path unavailable, or 0x0B, target device failed to respond, which the gateway generates when the pump is silent); malformed reply (cannot be decoded as a Modbus frame); mismatched reply (unit id, function code or transaction id differs from the request); wrong number of values; connection lost.
  - **not attempted**: the run ended before the block was read.

  When the extended flag is absent, extended blocks are not part of the run: they have no outcome and appear in neither the report, the counts nor the transcript.
- **Interrupt**: SIGINT (Ctrl-C) or SIGTERM (as sent by `docker stop`). Both are treated the same.

## Requirements

### Requirement 1: Connecting to the gateway

**User story:** As the maintainer, I want to point the probe at my gateway from the command line, so that I can run it without writing a config file.

#### Acceptance criteria

1. THE SYSTEM SHALL accept the gateway host as a required command-line argument.
2. THE SYSTEM SHALL accept the TCP port, the Modbus unit id and the reply timeout as optional command-line arguments, defaulting to port 4196, unit id 1 and a timeout of 3 seconds.
3. IF the port is outside 1–65535, the unit id is outside 1–247, or the timeout is outside 0.5–30 seconds, THEN THE SYSTEM SHALL exit with status 2 and a message naming the invalid argument, without opening a connection.
4. THE SYSTEM SHALL open at most one TCP connection per run and close it before exiting, including when the run is aborted or interrupted.
5. IF the connection cannot be established within the timeout, THEN THE SYSTEM SHALL exit with status 2 and a message naming the host and port, without retrying.
6. THE SYSTEM SHALL complete every check that can end the run with status 2 without a connection (argument validation, the output-path check of Requirement 8.4, and the interactivity check of Requirement 4.5) before showing the confirmation prompt.

### Requirement 2: Read-only guarantee

**User story:** As the owner of the heat pump, I want it to be impossible for the probe to change anything on the pump, so that I can run it on an unverified map without risk.

#### Acceptance criteria

1. THE SYSTEM SHALL issue only Modbus function codes 01, 02, 03 and 04.
2. THE SYSTEM SHALL NOT offer any command-line option or environment variable that changes the set of function codes issued.
3. IF a request with a function code other than 01, 02, 03 or 04 is submitted to the probe's request sender, THEN THE SYSTEM SHALL reject it before anything is sent.

### Requirement 3: Bus rules

**User story:** As the owner of the heat pump, I want the probe to follow the vendor's bus rules, so that the readings are trustworthy and the pump's controller is not upset.

#### Acceptance criteria

1. THE SYSTEM SHALL read coils and discrete inputs only in blocks of 48 and input and holding registers only in blocks of 3.
2. THE SYSTEM SHALL start every read at the first address of a standard block or an extended block as listed under Terms, and at no other address.
3. THE SYSTEM SHALL send requests strictly one at a time, sending the next request only after the previous one has been answered or has timed out.
4. THE SYSTEM SHALL wait at least 60 ms between the end of one request (reply received or timeout elapsed) and the start of the next.
5. WHEN a malformed or mismatched reply is received, THE SYSTEM SHALL record the block as failed at once, without waiting for a further reply.
6. WHEN a block's outcome is failed for any reason other than connection lost, THE SYSTEM SHALL wait at least 1 second before sending the next request, and SHALL discard anything received during that wait.
7. THE SYSTEM SHALL NOT attribute a reply to any request other than the one it answers. WHEN a reply carries the transaction id of an earlier request, THE SYSTEM SHALL discard it and keep waiting for the pending request's reply until that request's timeout; such a reply is not a mismatched reply.
8. THE SYSTEM SHALL NOT retry a block, whatever its outcome.

### Requirement 4: Confirming the preconditions

**User story:** As the maintainer, I want to be reminded of the bus preconditions before anything is sent, so that I do not run the probe with a second master on the bus.

#### Acceptance criteria

1. WHEN the probe starts without the confirmation flag, THE SYSTEM SHALL print the preconditions (the stock WiFi module is unplugged, the controller container is stopped, no other client is connected to the gateway) and prompt for confirmation before opening a connection.
2. WHEN the maintainer answers the prompt with exactly `yes`, THE SYSTEM SHALL proceed.
3. IF the answer is anything else, including empty input and end of input, THEN THE SYSTEM SHALL exit with status 2 without opening a connection. An interrupt at the prompt is not an answer; Requirement 9.1 gives its status.
4. WHEN the probe starts with the confirmation flag, THE SYSTEM SHALL skip the prompt.
5. IF standard input is not interactive and the confirmation flag is absent, THEN THE SYSTEM SHALL exit with status 2 and a message naming the flag, without opening a connection.

### Requirement 5: Reading the standard blocks

**User story:** As the maintainer, I want the probe to read everything the vendor says is readable, so that one run gives me the full picture.

#### Acceptance criteria

1. WHEN the probe runs, THE SYSTEM SHALL read every standard block exactly once, in this order: coils, discrete inputs, holding registers, input registers, each in ascending address order.
2. WHEN a block's outcome is ok, THE SYSTEM SHALL record the raw value of every address in the block, including addresses that are reserved or absent from the map.
3. WHEN a block's outcome is refused, THE SYSTEM SHALL record the Modbus exception code and continue with the next block.
4. WHEN a block's outcome is failed, THE SYSTEM SHALL record the reason and continue with the next block, subject to criterion 5.
5. IF two blocks in a row have the outcome failed, THEN THE SYSTEM SHALL abort the run, record every block not yet read as not attempted, and still produce the report. A refused block does not count towards this limit and resets the count.
6. IF the connection is lost during the run, THEN THE SYSTEM SHALL NOT reconnect. The block in progress is recorded as failed; when the loss is noticed between two blocks, the next block is recorded as failed. All later blocks are recorded as not attempted.

### Requirement 6: Reading the extended blocks

**User story:** As the maintainer, I want to find out whether the registers outside the vendor's labelled addresses are readable on my unit, without that being the default behaviour.

#### Acceptance criteria

1. WHEN the probe runs without the extended flag, THE SYSTEM SHALL NOT read any extended block.
2. WHEN the probe runs with the extended flag, THE SYSTEM SHALL read every extended block exactly once, after all standard blocks, in the order holding registers then input registers, each in ascending address order.
3. IF the standard blocks were aborted under Requirement 5.5 or 5.6, THEN THE SYSTEM SHALL NOT read any extended block.
4. THE SYSTEM SHALL apply Requirements 5.2 to 5.6 to extended blocks, counting consecutive failed blocks afresh from the first extended block.
5. THE SYSTEM SHALL report extended blocks in a section separate from the standard blocks, labelled as outside the vendor's allowed first addresses and as unverified.

### Requirement 7: The report

**User story:** As the maintainer, I want a report I can read next to the pump's display, so that I can tell quickly whether the map matches my unit.

#### Acceptance criteria

1. THE SYSTEM SHALL print, for each block, its table, first address and outcome, and for an ok block the raw value of every address in it.
2. THE SYSTEM SHALL print, for each address that has an entry in the project's register map, the register key, its name, the raw value, the decoded value with its unit, and the register's notes, using the project's codec for decoding.
3. THE SYSTEM SHALL print, for holding registers 0 and 1, the name of the operating mode and power mode that the raw value represents, or "unknown" when the value is not a defined mode.
4. THE SYSTEM SHALL print the active faults from the discrete input block at address 48, with code, kind and description, or "none" when that block is ok and no fault bit is set.
5. THE SYSTEM SHALL mark a value as "suspect" when any of these holds: its raw value lies outside the register's defined raw range; its raw value is off the register's raw step counted from its raw minimum; it is a decoded temperature outside −40 °C to 120 °C; it is a raw 0 on input registers 15 to 20, where 0 means unsupported.
6. THE SYSTEM SHALL print a summary section of the values to compare with the pump's display, naming each register: `power` (coil 0) and `running` (discrete input 0); `operating_mode`; `power_mode`; the setpoint register of the active operating mode; `inlet_temp`, `outlet_temp` and `ambient_temp`.
7. IF the operating mode is unknown or unavailable, THEN THE SYSTEM SHALL show all three setpoint registers in the summary.
8. WHEN both `compressor_current` and `pfc_voltage` were read, THE SYSTEM SHALL print the estimated compressor power in W, labelled as estimated.
9. WHEN the extended flag is set, THE SYSTEM SHALL also print input registers 21 to 25 (board version) and 26 to 29 (model code) as text, labelled as unverified. Because the encoding is unverified, each is printed in two renderings: one character per register taken from the low byte, and two characters per register taken from the high byte then the low byte. A byte that is not printable ASCII is shown as a placeholder, and a register from a block that is not ok is shown as unavailable.
10. THE SYSTEM SHALL print the counts of blocks ok, refused, failed and not attempted, separately for standard and extended blocks, and SHALL state how the run ended using the same four values as Requirement 8.1.
11. IF a block is refused, failed or not attempted, THEN THE SYSTEM SHALL show everything derived from it as unavailable, including its registers, the fault list, the summary items and the power estimate, and SHALL NOT show a stale, default or zero value in its place.

### Requirement 8: The transcript

**User story:** As the maintainer, I want the run saved in a machine-readable file, so that I can keep it as evidence and later specs can use it as a test fixture.

#### Acceptance criteria

1. WHEN an output path is given, THE SYSTEM SHALL write a JSON transcript to that path containing exactly: a transcript format version, the probe version, the start time in UTC, the port, unit id and timeout, whether the extended flag was set, how the run ended (complete, aborted after consecutive failures, aborted on connection loss, or interrupted), and for every block in the run its table, first address, count, whether it is extended, outcome, failure reason or exception code if any, and raw values.
2. THE SYSTEM SHALL NOT write the gateway host, credentials or any other site-specific value to the transcript, so that a transcript can be committed as a test fixture unchanged.
3. THE SYSTEM SHALL write the transcript when the run is aborted or interrupted after connecting, containing the blocks read so far and the blocks not attempted.
4. IF the output path already exists and the overwrite flag is absent, or its directory does not exist or is not writable, THEN THE SYSTEM SHALL exit with status 2 before opening a connection.
5. IF the transcript cannot be written, THEN THE SYSTEM SHALL print the report as normal and print the write error.

### Requirement 9: Exit status

**User story:** As the maintainer, I want the exit status to tell me whether the run was complete and its evidence saved, so that I can use the probe in a script.

#### Acceptance criteria

1. THE SYSTEM SHALL choose the exit status by the first of these rules that applies:
   1. status 130 when the maintainer interrupted the run, at any point from the confirmation prompt onwards;
   2. status 2 when the run could not start: invalid arguments, a declined or impossible confirmation, an existing output path, or a failed connection;
   3. status 1 when any standard block is refused, failed or not attempted, or a requested transcript could not be written;
   4. status 0 otherwise.
2. THE SYSTEM SHALL NOT let the outcome of any extended block affect the exit status.
3. WHEN the maintainer interrupts the run after the connection is open, THE SYSTEM SHALL stop sending requests, close the connection, and produce the report and any requested transcript for the blocks read so far before exiting.

### Requirement 10: Running the probe

**User story:** As the maintainer, I want to run the probe from a checkout or from the Docker image, so that I can use whichever machine can reach the gateway.

#### Acceptance criteria

1. THE SYSTEM SHALL provide the probe as a module inside the `app` package that is invocable with `python -m`, so that it is available both in a development checkout and in the Docker image, which ships only that package.
2. WHEN run with the help flag, THE SYSTEM SHALL print its usage, including the preconditions of Requirement 4 and the meaning of each exit status, and exit with status 0 without opening a connection.

## Constraints

These bind the design and the tasks. They are not acceptance criteria.

1. **Testable without hardware.** Every acceptance criterion above must be provable by an automated test against a substitute for the Modbus connection. No test opens a network connection, and the request spacing and the post-timeout wait must be testable without real delays.
2. **Single source for the map.** Block sizes, register definitions, decoding and fault decoding come from `app/modbus/registers.py`, `codec.py` and `faults.py`. The probe does not restate them; the labels for input registers 21 to 31, which are not in the map, are the probe's own and are marked unverified. The list of standard first addresses is added to `registers.py`, covered by the map doc check, so that spec 002's client uses the same list. The extended list belongs to the probe alone.
3. **One request sender, under `app/modbus/`.** All probe requests pass through one object, which is where Requirement 2.3 is enforced. It and the rest of the probe live under `app/modbus/`, so that the safety review triggers on any change to them and `AGENTS.md`'s rule that only `app/modbus/` builds Modbus requests holds. Spec 002 decides whether its client reuses this sender.
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

# Part 2: Design

## Overview

The probe does not use `pymodbus`. It speaks Modbus TCP itself over an asyncio stream, with a framing layer that can only encode the four read function codes. This gives direct control over transaction ids, late replies and timing, which the requirements depend on, and makes the read-only guarantee structural.

```
python -m app.modbus.probe
  cli (main)            arguments, pre-checks, prompt, signals, exit status
   └─ run_probe         block order, abort rules, extended rules
       └─ ReadOnlyLink  one request at a time, spacing, quiet wait, outcomes
           └─ ByteStream (TcpByteStream in production, a fake in tests)
  render_report / build_transcript   pure functions over the ProbeRun
```

## Files

| Path | Action | Content |
|---|---|---|
| `app/modbus/registers.py` | modify | Add `STANDARD_BLOCK_STARTS` |
| `scripts/render_modbus_map.py` | modify | Render a `read_blocks` generated block |
| `docs/modbus-map.md` | modify | Replace the hand-written table under bus rule 1 with the `read_blocks` generated block |
| `app/modbus/readonly_link.py` | create | Framing, `ByteStream`, `TcpByteStream`, `ReadOnlyLink`, result types |
| `app/modbus/probe.py` | create | Block plan, `run_probe`, CLI `main`, `__main__` guard |
| `app/modbus/probe_report.py` | create | `render_report`, `build_transcript` |
| `tests/unit/fakes.py` | create | `FakeStream`, `FakeClock` |
| `tests/unit/test_registers.py` | modify | Tests for `STANDARD_BLOCK_STARTS` |
| `tests/unit/test_readonly_link.py` | create | Framing and link tests |
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
    TIMEOUT = "timeout"
    GATEWAY_EXCEPTION = "gateway_exception"
    MALFORMED = "malformed_reply"
    MISMATCHED = "mismatched_reply"
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

class ConnectionLost(Exception): ...

class ByteStream(Protocol):
    async def write(self, data: bytes) -> None: ...                    # raises ConnectionLost
    async def read_exactly(self, n: int, timeout: float) -> bytes: ...  # raises TimeoutError, ConnectionLost
    async def discard_for(self, seconds: float) -> None: ...            # read and drop input for this long; raises ConnectionLost
    async def close(self) -> None: ...
```

### Framing (pure functions)

```python
READ_FUNCTION_CODES: frozenset[int] = frozenset({0x01, 0x02, 0x03, 0x04})
GATEWAY_EXCEPTION_CODES: frozenset[int] = frozenset({0x0A, 0x0B})
MAX_PDU_LENGTH = 253

def build_request(transaction_id: int, unit_id: int, function_code: int, address: int, count: int) -> bytes
```

Raises `ValueError` when `function_code` is not in `READ_FUNCTION_CODES`. This is the single enforcement point of Requirement 2.3. Returns 12 bytes, big-endian: transaction id (2), protocol id `0x0000` (2), length `0x0006` (2), unit id (1), function code (1), address (2), count (2).

```python
@dataclass(frozen=True, slots=True)
class Header:
    transaction_id: int
    protocol_id: int
    length: int        # unit id + PDU
    unit_id: int

def parse_header(data: bytes) -> Header     # data is exactly 7 bytes
def decode_bits(payload: bytes, count: int) -> tuple[int, ...]       # LSB first within each byte
def decode_registers(payload: bytes) -> tuple[int, ...]              # big-endian unsigned 16-bit
```

### `TcpByteStream`

```python
class TcpByteStream:
    @classmethod
    async def open(cls, host: str, port: int, timeout: float) -> "TcpByteStream"
```

`open` wraps `asyncio.wait_for(asyncio.open_connection(host, port), timeout)` and raises `OSError` (including `TimeoutError`) on failure. `read_exactly` wraps `reader.readexactly` in `asyncio.wait_for`; `asyncio.IncompleteReadError`, `ConnectionError` and `OSError` other than `TimeoutError` become `ConnectionLost`. `write` writes and drains, mapping `ConnectionError`/`OSError` to `ConnectionLost`. `discard_for` reads up to 256 bytes at a time until the period elapses, mapping end of stream to `ConnectionLost`. `close` closes the writer and awaits `wait_closed`, swallowing `OSError`. Tests patch `asyncio.open_connection`; no socket is opened.

### `ReadOnlyLink`

```python
MIN_GAP_S = MIN_REQUEST_GAP_S          # 0.06, from registers.py
QUIET_AFTER_FAILURE_S = 1.0

class ReadOnlyLink:
    def __init__(self, stream: ByteStream, *, unit_id: int, timeout: float,
                 allowed: frozenset[BlockSpec],
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
                 monotonic: Callable[[], float] = time.monotonic) -> None
    async def read_block(self, spec: BlockSpec) -> BlockResult
    async def close(self) -> None
    @property
    def connection_lost(self) -> bool
```

`read_block` never raises for bus conditions; it always returns a `BlockResult`. It raises `ValueError`, before writing anything, when `spec` is not in `allowed` (Requirement 3.2 by construction) or when `build_request` rejects the function code (Requirement 2.3). Algorithm:

1. If `spec not in allowed`, raise `ValueError`. If `connection_lost` is already true, return `FAILED / CONNECTION_LOST` without writing.
2. If a previous request ended less than `MIN_GAP_S` ago by `monotonic()`, `await sleep(remaining)`.
3. Increment the transaction id (16-bit, starting at 1), build the request with `READ_FUNCTION_CODE[spec.table]`, `spec.start`, `spec.count`, and write it. Set `deadline = monotonic() + timeout`.
4. Loop: read 7 header bytes with timeout `deadline - monotonic()` (if that is ≤ 0, the result is `TIMEOUT`).
   - `protocol_id != 0`, or `length < 3`, or `length > MAX_PDU_LENGTH + 1` → `MALFORMED`.
   - Otherwise read the `length - 1` PDU bytes within the same deadline.
   - If the transaction id is one issued earlier by this link (lower than the pending id, allowing for wrap-around: `(pending - tid) % 65536` between 1 and 32767) → discard and continue the loop. This test also matches ids this link never issued; such a stray frame is discarded too and the block then ends as `TIMEOUT`, which is still a failed outcome.
   - If the transaction id or the unit id differs otherwise → `MISMATCHED`.
   - If the PDU's first byte is `function_code | 0x80` and the PDU is 2 bytes: code in `GATEWAY_EXCEPTION_CODES` → `FAILED / GATEWAY_EXCEPTION` with `exception_code`; any other code → `REFUSED` with `exception_code`.
   - If the first byte is not the request's function code → `MISMATCHED`.
   - Expected payload length is 6 bytes for every block (48 bits, or 3 registers). If the byte-count field or the actual payload length differs → `WRONG_LENGTH`.
   - Otherwise decode and return `OK`.
5. `TimeoutError` → `TIMEOUT`. `ConnectionLost` at any step → set `connection_lost`, return `CONNECTION_LOST`.
6. Record the end time. If the outcome is `FAILED` with a reason other than `CONNECTION_LOST`, `await stream.discard_for(QUIET_AFTER_FAILURE_S)` before returning; a `ConnectionLost` raised there sets `connection_lost` and does not change the result.

Because `discard_for` runs inside `read_block`, the next request is at least 1 s after a failure (Requirement 3.6), and step 2 guarantees the 60 ms gap otherwise (Requirement 3.4). `read_block` is awaited sequentially by `run_probe`, which gives Requirement 3.3.

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
         open_stream: Callable[[str, int, float], Awaitable[ByteStream]] = TcpByteStream.open,
         install_interrupt: InstallInterrupt = install_signal_handlers) -> int

def install_signal_handlers(on_interrupt: Callable[[], None]) -> None
async def _run(args: argparse.Namespace, open_stream, should_stop: Callable[[], bool]) -> ProbeRun
```

The module ends with `if __name__ == "__main__": raise SystemExit(main())`.

Streams: the preconditions, the prompt and the report go to `stdout`; every error message goes to `stderr`. The one exception is argparse: `--help` and usage errors are written by argparse to `sys.stdout`/`sys.stderr` and leave `main` as `SystemExit` (0 for help, 2 for a usage error). Tests for those use `pytest.raises(SystemExit)` and `capsys`.

### Interrupt handling

`main` owns one piece of state: `interrupted: bool` and `phase`, one of `"waiting"` or `"running"`.

- `install_signal_handlers` registers one handler for `SIGINT` and `SIGTERM` with `signal.signal`; the handler calls `on_interrupt()`.
- `on_interrupt` sets `interrupted = True`. If `phase` is `"waiting"` it then raises `KeyboardInterrupt`; if `"running"` it returns, and the run stops at the next block boundary through `should_stop`.
- `phase` is `"waiting"` from installation until the stream is open, covering the prompt and the connection attempt, and `"running"` from then until `run_probe` returns.
- `main` catches `KeyboardInterrupt` around the prompt and around `asyncio.run` and returns 130.
- After `run_probe` returns, if `interrupted` is true `main` replaces the run's end with `dataclasses.replace(run, end=RunEnd.INTERRUPTED)`, whatever `run_probe` decided. So an interrupt during the last block, or during a block that also triggers an abort, is reported and exits as interrupted.
- An interrupt while a block is in flight lets that block finish (at most one timeout), then stops.

Tests never send a real signal. They pass their own `install_interrupt`, keep the callback it receives, and call it at the chosen moment: from a fake `stdin.readline` for the prompt, from a fake `open_stream` for the connection attempt, and from `FakeStream`'s `on_request` hook during a run.

### Order of operations

Each step returns the stated status on failure.

1. Parse arguments with `argparse`. The epilog lists the three preconditions and the four exit statuses.
2. Validate ranges: port 1–65535, unit id 1–247, timeout 0.5–30. → 2, message names the argument.
3. If `--output` is given: the path must not exist unless `--overwrite`; its parent directory must exist and be writable (`os.access(parent, os.W_OK)`). → 2.
4. If `--yes` is absent and `stdin.isatty()` is false → 2, message names `--yes`.
5. Call `install_interrupt(on_interrupt)`.
6. If `--yes` is absent: print the preconditions and a prompt, read one line with `stdin.readline()`; proceed only if `line.rstrip("\r\n") == "yes"`. Anything else, including end of input (an empty string) → 2.
7. `asyncio.run(_run(...))`. `_run` opens the stream (an `OSError` propagates to `main`, which prints a message naming host and port and returns 2), sets `phase = "running"`, builds a `ReadOnlyLink` with `allowed` set to the run's plan, awaits `run_probe`, and closes the link in a `finally`.
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

Plain text, sections in this order, each starting with the heading shown. This example is a run with the extended flag in which holding block 15 was refused and input block 9 timed out.

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
[failed: timeout] input 9-11

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
- **Bit blocks:** only addresses with a map entry get a line, followed by one line `other bits set: <addresses joined with ", ">` or `other bits set: none`. Discrete input block 48 lists no addresses and shows `see Active faults`.
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

## Open questions and assumptions

- **No `pymodbus` in the probe.** The probe frames Modbus TCP itself because it needs control over transaction ids, late replies and timing that `pymodbus` does not expose, and because a layer that can only encode reads makes the read-only guarantee structural. Whether the controller's client (spec 002) reuses `ReadOnlyLink`'s framing or uses `pymodbus` is for spec 002. Task 11 records this in `docs/design-decisions.md`.
- **Gateway behaviour is assumed, not known.** The design assumes the Waveshare gateway echoes the request's transaction id and unit id in each reply, and that a late RTU reply, if forwarded at all, carries the id of the request it answers. If the gateway instead stamps a late reply with the current id, the 1 s quiet wait after a timeout is the only protection. The first live run will show which.
- **Gateway exception codes.** Whether the gateway returns 0x0B or simply stays silent when the pump does not answer is unknown. Both are handled as failed.

## Test strategy

- `tests/unit/fakes.py`:
  - `FakeClock`: `monotonic()` returns a float; `async sleep(s)` advances it and records the call.
  - `FakeStream(clock, on_request=None)`: scripted with a list of actions per expected request (`reply(bytes)`, `timeout()`, `lost()`, `late(bytes)` to queue bytes ahead of the real reply). `on_request(index)` is called when the request with that zero-based index is written, which is how tests trigger an interrupt mid-run. Records every written request with the clock time, and every `discard_for` call (which advances the clock). Reply helpers build valid frames from a request so tests stay short.
  - `FakeLink`: a `BlockReader` returning scripted `BlockResult`s and recording the specs it was asked for.
- No test opens a socket. `TcpByteStream` is tested by patching `asyncio.open_connection` with fake reader and writer objects.
- Timing is asserted from the recorded clock times, never with real sleeps.
- Properties (hypothesis):
  - `build_request` rejects every function code outside `{1, 2, 3, 4}` for any other arguments.
  - For any sequence of scripted outcomes, `run_probe` returns exactly one result per planned block, in plan order, and never asks the link for a block not in the plan.
  - For any sequence of scripted outcomes, every request `FakeStream` records starts at least 0.06 s after the previous one ended.
  - `decode_registers(encode(values)) == values` for any three 16-bit values, and the same for 48 bits.

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

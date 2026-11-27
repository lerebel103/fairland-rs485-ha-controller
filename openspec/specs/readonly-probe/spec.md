# readonly-probe Specification

## Purpose

A one-shot, read-only command-line probe. It connects to the pump through the RS485 gateway, reads the register map once using only the vendor's read shapes, and reports raw and decoded values so the maintainer can verify the map on the AXCR21V. It never writes to the pump and is not part of the running controller.

The probe may read the extended blocks below, which start outside the vendor's labelled first addresses. This is the one exception to the bus rule on allowed first addresses (decided 2026-11-26; see `docs/design-decisions.md`). It is probe-only and opt-in.

A reference such as "Requirement 5.5" means scenario 5.5, that is, criterion 5 of requirement R5. The design and task list are in `openspec/changes/archive/2026-11-27-readonly-probe/`.

### Terms

- **Standard block**: a read of the vendor's fixed count starting at a first address the vendor table labels as allowed. The complete list is: coils 0; discrete inputs 0 and 48; holding registers 0, 3, 6, 9, 12, 15, 18; input registers 0, 3, 6, 9, 12.
- **Extended block**: a read of the vendor's fixed count starting at one of the addresses in this list, which is the complete and normative definition: holding register 24; input registers 15, 18, 21, 24, 27, 30. These are the blocks that `docs/modbus-map.md` asks the probe to settle, and no others. Holding block 21 is excluded: its only basis is an older table revision's expansion-valve settings, which the map deliberately leaves out. Input block 30 covers addresses 30 to 32, and no source documents address 32.
- **Block outcome**: exactly one of the following.
  - **ok**: a valid reply with the expected number of values.
  - **refused**: a valid Modbus exception response other than codes 0x0A and 0x0B. The pump answered and declined.
  - **failed**: no usable answer from the pump. The reasons are: no reply (no valid reply within the timeout; this includes silence and any frame the Modbus library discards as malformed or as not matching the request); gateway exception (code 0x0A, gateway path unavailable, or 0x0B, target device failed to respond, which the gateway generates when the pump is silent); wrong number of values; connection lost.
  - **not attempted**: the run ended before the block was read.

  When the extended flag is absent, extended blocks are not part of the run: they have no outcome and appear in neither the report, the counts nor the transcript.
- **Interrupt**: SIGINT (Ctrl-C) or SIGTERM (as sent by `docker stop`). Both are treated the same.

## Requirements

### Requirement: Connecting to the gateway (R1)
The probe SHALL connect to the gateway from command-line arguments alone, with no config file.

#### Scenario: 1.1
- **WHEN** the probe runs
- **THEN** the system SHALL accept the gateway host as a required command-line argument.

#### Scenario: 1.2
- **WHEN** the probe runs
- **THEN** the system SHALL accept the TCP port, the Modbus unit id and the reply timeout as optional command-line arguments, defaulting to port 4196, unit id 1 and a timeout of 3 seconds.

#### Scenario: 1.3
- **WHEN** the port is outside 1–65535, the unit id is outside 1–247, or the timeout is outside 0.5–30 seconds
- **THEN** the system SHALL exit with status 2 and a message naming the invalid argument, without opening a connection.

#### Scenario: 1.4
- **WHEN** the probe runs
- **THEN** the system SHALL open at most one TCP connection per run and close it before exiting, including when the run is aborted or interrupted.

#### Scenario: 1.5
- **WHEN** the connection cannot be established within the timeout
- **THEN** the system SHALL exit with status 2 and a message naming the host and port, without retrying.

#### Scenario: 1.6
- **WHEN** the probe runs
- **THEN** the system SHALL complete every check that can end the run with status 2 without a connection (argument validation, the output-path check of Requirement 8.4, and the interactivity check of Requirement 4.5) before showing the confirmation prompt.

### Requirement: Read-only guarantee (R2)
The probe SHALL be unable to change anything on the pump.

#### Scenario: 2.1
- **WHEN** the probe runs
- **THEN** the system SHALL issue only Modbus function codes 01, 02, 03 and 04.

#### Scenario: 2.2
- **WHEN** the probe runs
- **THEN** the system SHALL NOT offer any command-line option or environment variable that changes the set of function codes issued.

#### Scenario: 2.3
- **WHEN** the probe runs
- **THEN** the system SHALL route every request through one request sender whose only operation is reading a block, and which calls only the four read operations of the Modbus library.

### Requirement: Bus rules (R3)
The probe SHALL follow the vendor's bus rules for read shapes, first addresses, spacing and one request at a time.

#### Scenario: 3.1
- **WHEN** the probe runs
- **THEN** the system SHALL read coils and discrete inputs only in blocks of 48 and input and holding registers only in blocks of 3.

#### Scenario: 3.2
- **WHEN** the probe runs
- **THEN** the system SHALL start every read at the first address of a standard block or an extended block as listed under Terms, and at no other address.

#### Scenario: 3.3
- **WHEN** the probe runs
- **THEN** the system SHALL send requests strictly one at a time, sending the next request only after the previous one has been answered or has timed out.

#### Scenario: 3.4
- **WHEN** the probe runs
- **THEN** the system SHALL wait at least 60 ms between the end of one request (reply received or timeout elapsed) and the start of the next.

#### Scenario: 3.5
- **WHEN** the probe runs
- **THEN** the system SHALL use Modbus TCP framing (MBAP header with transaction ids), not RTU over TCP, and SHALL rely on the Modbus library to match each reply to its request by transaction id, so that a reply is never attributed to another request.

#### Scenario: 3.6
- **WHEN** a block's outcome is failed for any reason other than connection lost
- **THEN** the system SHALL wait at least 1 second before sending the next request.

#### Scenario: 3.7
- **WHEN** the probe runs
- **THEN** the system SHALL NOT retry a block, whatever its outcome, and SHALL disable the Modbus library's automatic retries and automatic reconnection.

### Requirement: Confirming the preconditions (R4)
The probe SHALL require the maintainer to confirm the bus preconditions before it opens a connection.

#### Scenario: 4.1
- **WHEN** the probe starts without the confirmation flag
- **THEN** the system SHALL print the preconditions (the stock WiFi module is unplugged, the controller container is stopped, no other client is connected to the gateway) and prompt for confirmation before opening a connection.

#### Scenario: 4.2
- **WHEN** the maintainer answers the prompt with exactly `yes`
- **THEN** the system SHALL proceed.

#### Scenario: 4.3
- **WHEN** the answer is anything else, including empty input and end of input
- **THEN** the system SHALL exit with status 2 without opening a connection. An interrupt at the prompt is not an answer; Requirement 9.1 gives its status.

#### Scenario: 4.4
- **WHEN** the probe starts with the confirmation flag
- **THEN** the system SHALL skip the prompt.

#### Scenario: 4.5
- **WHEN** standard input is not interactive and the confirmation flag is absent
- **THEN** the system SHALL exit with status 2 and a message naming the flag, without opening a connection.

### Requirement: Reading the standard blocks (R5)
The probe SHALL read every standard block once and record each block's outcome.

#### Scenario: 5.1
- **WHEN** the probe runs
- **THEN** the system SHALL read every standard block exactly once, in this order: coils, discrete inputs, holding registers, input registers, each in ascending address order.

#### Scenario: 5.2
- **WHEN** a block's outcome is ok
- **THEN** the system SHALL record the raw value of every address in the block, including addresses that are reserved or absent from the map.

#### Scenario: 5.3
- **WHEN** a block's outcome is refused
- **THEN** the system SHALL record the Modbus exception code and continue with the next block.

#### Scenario: 5.4
- **WHEN** a block's outcome is failed
- **THEN** the system SHALL record the reason and continue with the next block, subject to criterion 5.

#### Scenario: 5.5
- **WHEN** two blocks in a row have the outcome failed
- **THEN** the system SHALL abort the run, record every block not yet read as not attempted, and still produce the report. A refused block does not count towards this limit and resets the count.

#### Scenario: 5.6
- **WHEN** the connection is lost during the run
- **THEN** the system SHALL NOT reconnect. The block in progress is recorded as failed; when the loss is noticed between two blocks, the next block is recorded as failed. All later blocks are recorded as not attempted.

### Requirement: Reading the extended blocks (R6)
The probe SHALL read the extended blocks only when asked, after the standard blocks, and report them as unverified.

#### Scenario: 6.1
- **WHEN** the probe runs without the extended flag
- **THEN** the system SHALL NOT read any extended block.

#### Scenario: 6.2
- **WHEN** the probe runs with the extended flag
- **THEN** the system SHALL read every extended block exactly once, after all standard blocks, in the order holding registers then input registers, each in ascending address order.

#### Scenario: 6.3
- **WHEN** the standard blocks were aborted under Requirement 5.5 or 5.6
- **THEN** the system SHALL NOT read any extended block.

#### Scenario: 6.4
- **WHEN** the probe runs
- **THEN** the system SHALL apply Requirements 5.2 to 5.6 to extended blocks, counting consecutive failed blocks afresh from the first extended block.

#### Scenario: 6.5
- **WHEN** the probe runs
- **THEN** the system SHALL report extended blocks in a section separate from the standard blocks, labelled as outside the vendor's allowed first addresses and as unverified.

### Requirement: The report (R7)
The probe SHALL print a report that can be compared with the pump's display.

#### Scenario: 7.1
- **WHEN** the probe runs
- **THEN** the system SHALL print, for each block, its table, first address and outcome, and for an ok block the raw value of every address in it. For a bit block the raw values may be printed as one string of 48 bits in address order.

#### Scenario: 7.2
- **WHEN** the probe runs
- **THEN** the system SHALL print, for each address that has an entry in the project's register map, the register key, its name, the raw value, the decoded value with its unit, and the register's notes, using the project's codec for decoding.

#### Scenario: 7.3
- **WHEN** the probe runs
- **THEN** the system SHALL print, for holding registers 0 and 1, the name of the operating mode and power mode that the raw value represents, or "unknown" when the value is not a defined mode.

#### Scenario: 7.4
- **WHEN** the probe runs
- **THEN** the system SHALL print the active faults from the discrete input block at address 48, with code, kind and description, or "none" when that block is ok and no fault bit is set.

#### Scenario: 7.5
- **WHEN** the probe runs
- **THEN** the system SHALL mark a value as "suspect" when any of these holds: its raw value lies outside the register's defined raw range; its raw value is off the register's raw step counted from its raw minimum; it is a decoded temperature outside −40 °C to 120 °C; it is a raw 0 on input registers 15 to 20, where 0 means unsupported.

#### Scenario: 7.6
- **WHEN** the probe runs
- **THEN** the system SHALL print a summary section of the values to compare with the pump's display, naming each register: `power` (coil 0) and `running` (discrete input 0); `operating_mode`; `power_mode`; the setpoint register of the active operating mode; `inlet_temp`, `outlet_temp` and `ambient_temp`.

#### Scenario: 7.7
- **WHEN** the operating mode is unknown or unavailable
- **THEN** the system SHALL show all three setpoint registers in the summary.

#### Scenario: 7.8
- **WHEN** both `compressor_current` and `pfc_voltage` were read
- **THEN** the system SHALL print the estimated compressor power in W, labelled as estimated.

#### Scenario: 7.9
- **WHEN** the extended flag is set
- **THEN** the system SHALL also print input registers 21 to 25 (board version) and 26 to 29 (model code) as text, labelled as unverified. Because the encoding is unverified, each is printed in two renderings: one character per register taken from the low byte, and two characters per register taken from the high byte then the low byte. A byte that is not printable ASCII is shown as a placeholder, and a register from a block that is not ok is shown as unavailable.

#### Scenario: 7.10
- **WHEN** the probe runs
- **THEN** the system SHALL print the counts of blocks ok, refused, failed and not attempted, separately for standard and extended blocks, and SHALL state how the run ended using the same four values as Requirement 8.1.

#### Scenario: 7.11
- **WHEN** a block is refused, failed or not attempted
- **THEN** the system SHALL show everything derived from it as unavailable, including its registers, the fault list, the summary items and the power estimate, and SHALL NOT show a stale, default or zero value in its place.

### Requirement: The transcript (R8)
The probe SHALL save the run as a machine-readable transcript that contains no site-specific value.

#### Scenario: 8.1
- **WHEN** an output path is given
- **THEN** the system SHALL write a JSON transcript to that path containing exactly: a transcript format version, the probe version, the start time in UTC, the port, unit id and timeout, whether the extended flag was set, how the run ended (complete, aborted after consecutive failures, aborted on connection loss, or interrupted), and for every block in the run its table, first address, count, whether it is extended, outcome, failure reason or exception code if any, and raw values.

#### Scenario: 8.2
- **WHEN** the probe runs
- **THEN** the system SHALL NOT write the gateway host, credentials or any other site-specific value to the transcript, so that a transcript can be committed as a test fixture unchanged.

#### Scenario: 8.3
- **WHEN** the probe runs
- **THEN** the system SHALL write the transcript when the run is aborted or interrupted after connecting, containing the blocks read so far and the blocks not attempted.

#### Scenario: 8.4
- **WHEN** the output path already exists and the overwrite flag is absent, or its directory does not exist or is not writable
- **THEN** the system SHALL exit with status 2 before opening a connection.

#### Scenario: 8.5
- **WHEN** the transcript cannot be written
- **THEN** the system SHALL print the report as normal and print the write error.

### Requirement: Exit status (R9)
The probe SHALL exit with a status that says whether the run was complete and its evidence saved.

#### Scenario: 9.1
- **WHEN** the probe runs
- **THEN** the system SHALL choose the exit status by the first of these rules that applies:
  1. status 130 when the maintainer interrupted the run, at any point from the confirmation prompt onwards;
  2. status 2 when the run could not start: invalid arguments, a declined or impossible confirmation, an existing output path, or a failed connection;
  3. status 1 when any standard block is refused, failed or not attempted, or a requested transcript could not be written;
  4. status 0 otherwise.

#### Scenario: 9.2
- **WHEN** the probe runs
- **THEN** the system SHALL NOT let the outcome of any extended block affect the exit status.

#### Scenario: 9.3
- **WHEN** the maintainer interrupts the run after the connection is open
- **THEN** the system SHALL stop sending requests, close the connection, and produce the report and any requested transcript for the blocks read so far before exiting.

### Requirement: Running the probe (R10)
The probe SHALL be runnable with `python -m` from a checkout and from the Docker image.

#### Scenario: 10.1
- **WHEN** the probe runs
- **THEN** the system SHALL provide the probe as a module inside the `app` package that is invocable with `python -m`, so that it is available both in a development checkout and in the Docker image, which ships only that package.

#### Scenario: 10.2
- **WHEN** run with the help flag
- **THEN** the system SHALL print its usage, including the preconditions of Requirement 4 and the meaning of each exit status, and exit with status 0 without opening a connection.

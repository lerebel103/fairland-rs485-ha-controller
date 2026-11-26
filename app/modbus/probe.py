"""Read-only probe of the heat pump through the RS485 gateway (spec 001).

Run with `python -m app.modbus.probe HOST`. The probe only ever issues Modbus read
function codes, one request at a time, and never writes to the pump.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import os
import signal
import sys
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol, TextIO

from app.modbus.readonly_link import (
    BlockResult,
    BlockSpec,
    FailReason,
    Outcome,
    ReadClient,
    ReadOnlyLink,
    open_client,
)
from app.modbus.registers import DEFAULT_UNIT_ID, STANDARD_BLOCK_STARTS, Table
from app.version import __version__

# Blocks outside the vendor's allowed first addresses that docs/modbus-map.md asks the probe to settle.
EXTENDED_BLOCK_STARTS: dict[Table, tuple[int, ...]] = {
    Table.HOLDING: (24,),
    Table.INPUT: (15, 18, 21, 24, 27, 30),
}
MAX_CONSECUTIVE_FAILURES = 2

_TABLE_ORDER = (Table.COIL, Table.DISCRETE_INPUT, Table.HOLDING, Table.INPUT)


class RunEnd(StrEnum):
    COMPLETE = "complete"
    ABORTED_FAILURES = "aborted_consecutive_failures"
    ABORTED_CONNECTION = "aborted_connection_lost"
    INTERRUPTED = "interrupted"


@dataclass(frozen=True, slots=True)
class ProbeRun:
    results: tuple[BlockResult, ...]  # one per block in the run, in plan order
    extended: bool
    end: RunEnd
    started_utc: datetime


def standard_plan() -> tuple[BlockSpec, ...]:
    return tuple(BlockSpec(t, s) for t in _TABLE_ORDER for s in STANDARD_BLOCK_STARTS.get(t, ()))


def extended_plan() -> tuple[BlockSpec, ...]:
    return tuple(BlockSpec(t, s, extended=True) for t in _TABLE_ORDER for s in EXTENDED_BLOCK_STARTS.get(t, ()))


class BlockReader(Protocol):
    async def read_block(self, spec: BlockSpec) -> BlockResult: ...


def _not_attempted(specs: tuple[BlockSpec, ...]) -> list[BlockResult]:
    return [BlockResult(spec, Outcome.NOT_ATTEMPTED) for spec in specs]


async def run_probe(
    link: BlockReader,
    *,
    extended: bool,
    should_stop: Callable[[], bool] = lambda: False,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> ProbeRun:
    started = now()
    plan = standard_plan() + (extended_plan() if extended else ())
    first_extended = len(standard_plan())
    results: list[BlockResult] = []
    failures = 0
    end = RunEnd.COMPLETE

    for index, spec in enumerate(plan):
        if should_stop():
            end = RunEnd.INTERRUPTED
            break
        if extended and index == first_extended:
            failures = 0
        result = await link.read_block(spec)
        results.append(result)
        if result.reason is FailReason.CONNECTION_LOST:
            end = RunEnd.ABORTED_CONNECTION
            break
        failures = failures + 1 if result.outcome is Outcome.FAILED else 0
        if failures >= MAX_CONSECUTIVE_FAILURES:
            end = RunEnd.ABORTED_FAILURES
            break

    results.extend(_not_attempted(plan[len(results) :]))
    return ProbeRun(tuple(results), extended, end, started)


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------

DEFAULT_PORT = 4196
EXIT_OK, EXIT_INCOMPLETE, EXIT_NOT_STARTED, EXIT_INTERRUPTED = 0, 1, 2, 130

_EPILOG = """\
Preconditions (confirm before the probe sends anything):
  - the stock WiFi module is unplugged
  - the controller container is stopped
  - no other client is connected to the gateway

The probe only reads. It never writes to the pump.

Exit status:
  0    every standard block was read ok
  1    a standard block was refused, failed or not attempted, or the transcript could not be written
  2    the run could not start: invalid arguments, declined confirmation, existing output path, failed connection
  130  interrupted (Ctrl-C or SIGTERM)
"""

InstallInterrupt = Callable[[Callable[[], None]], None]
OpenClient = Callable[[str, int, float], Awaitable[ReadClient]]


def install_signal_handlers(on_interrupt: Callable[[], None]) -> None:
    def handler(signum: int, frame: object) -> None:
        on_interrupt()

    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.modbus.probe",
        description="Read-only probe of a Fairland heat pump through an RS485 Modbus TCP gateway.",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("host", help="gateway host name or address")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="gateway TCP port (default %(default)s)")
    parser.add_argument("--unit-id", type=int, default=DEFAULT_UNIT_ID, help="Modbus unit id (default %(default)s)")
    parser.add_argument("--timeout", type=float, default=3.0, help="reply timeout in seconds (default %(default)s)")
    parser.add_argument("--extended", action="store_true", help="also read the unverified extended blocks")
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    parser.add_argument("--output", metavar="PATH", help="write a JSON transcript to PATH")
    parser.add_argument("--overwrite", action="store_true", help="allow --output to replace an existing file")
    return parser


def _invalid(args: argparse.Namespace) -> str | None:
    if not 1 <= args.port <= 65535:
        return "--port must be between 1 and 65535"
    if not 1 <= args.unit_id <= 247:
        return "--unit-id must be between 1 and 247"
    if not 0.5 <= args.timeout <= 30:
        return "--timeout must be between 0.5 and 30 seconds"
    return None


def _output_path_error(path: str, overwrite: bool) -> str | None:
    target = Path(path)
    if target.is_dir():
        return f"--output: {path} is a directory"
    if target.exists() and not overwrite:
        return f"--output: {path} already exists (use --overwrite to replace it)"
    parent = target.parent if str(target.parent) else Path(".")
    if not parent.is_dir():
        return f"--output: directory {parent} does not exist"
    if not os.access(parent, os.W_OK):
        return f"--output: directory {parent} is not writable"
    return None


async def _run(
    args: argparse.Namespace,
    open: OpenClient,  # noqa: A002
    should_stop: Callable[[], bool],
    on_connected: Callable[[], None],
) -> ProbeRun:
    client = await open(args.host, args.port, args.timeout)
    try:
        on_connected()
        plan = standard_plan() + (extended_plan() if args.extended else ())
        link = ReadOnlyLink(client, unit_id=args.unit_id, allowed=frozenset(plan))
        return await run_probe(link, extended=args.extended, should_stop=should_stop)
    finally:
        client.close()


def main(
    argv: Sequence[str] | None = None,
    *,
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
    open: OpenClient = open_client,  # noqa: A002
    install_interrupt: InstallInterrupt = install_signal_handlers,
) -> int:
    from app.modbus.probe_report import build_transcript, render_report

    args = _parser().parse_args(argv)

    def fail(message: str) -> int:
        print(f"error: {message}", file=stderr)
        return EXIT_NOT_STARTED

    if (message := _invalid(args)) is not None:
        return fail(message)
    if args.output and (message := _output_path_error(args.output, args.overwrite)):
        return fail(message)
    if not args.yes and not stdin.isatty():
        return fail("standard input is not interactive; pass --yes to confirm the preconditions")

    state = {"interrupted": False, "phase": "waiting"}

    def on_interrupt() -> None:
        state["interrupted"] = True
        if state["phase"] == "waiting":
            raise KeyboardInterrupt

    def on_connected() -> None:
        state["phase"] = "running"

    install_interrupt(on_interrupt)

    try:
        if not args.yes:
            print(_PRECONDITIONS, file=stdout)
            print('Type "yes" to continue: ', end="", file=stdout, flush=True)
            if stdin.readline().rstrip("\r\n") != "yes":
                return fail("confirmation declined; nothing was sent")
        run = asyncio.run(_run(args, open, lambda: state["interrupted"], on_connected))
    except KeyboardInterrupt:
        return EXIT_INTERRUPTED
    except OSError:
        return fail(f"could not connect to {args.host}:{args.port}")

    if state["interrupted"]:
        run = dataclasses.replace(run, end=RunEnd.INTERRUPTED)
    print(render_report(run), file=stdout)

    transcript_failed = False
    if args.output:
        transcript = build_transcript(
            run, port=args.port, unit_id=args.unit_id, timeout_s=args.timeout, probe_version=__version__
        )
        try:
            with Path(args.output).open("w" if args.overwrite else "x") as handle:
                handle.write(json.dumps(transcript, indent=2) + "\n")
        except OSError as exc:
            print(f"error: could not write the transcript: {exc}", file=stderr)
            transcript_failed = True

    if state["interrupted"]:
        return EXIT_INTERRUPTED
    standard_ok = all(r.outcome is Outcome.OK for r in run.results if not r.spec.extended)
    return EXIT_OK if standard_ok and not transcript_failed else EXIT_INCOMPLETE


_PRECONDITIONS = """\
Before the probe sends anything, confirm that:
  - the stock WiFi module is unplugged
  - the controller container is stopped
  - no other client is connected to the gateway"""


if __name__ == "__main__":
    raise SystemExit(main())

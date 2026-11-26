"""Report and transcript for the read-only probe (spec 001). Both are pure functions."""

from __future__ import annotations

from datetime import UTC
from typing import Any

from app.modbus.codec import decode
from app.modbus.faults import FAULT_BLOCK_START, decode_faults
from app.modbus.probe import ProbeRun, RunEnd
from app.modbus.readonly_link import BlockResult, FailReason, Outcome
from app.modbus.registers import (
    Codec,
    OperatingMode,
    PowerMode,
    Register,
    Table,
    by_table,
    get,
)

TRANSCRIPT_FORMAT_VERSION = 1

_RUN_END_TEXT = {
    RunEnd.COMPLETE: "complete",
    RunEnd.ABORTED_FAILURES: "aborted after consecutive failures",
    RunEnd.ABORTED_CONNECTION: "aborted on connection loss",
    RunEnd.INTERRUPTED: "interrupted",
}
_SETPOINT_BY_MODE = {0: "target_temp_auto", 1: "target_temp_heating", 2: "target_temp_cooling"}
_TEMP_CODECS = (Codec.TEMP_TYPE1, Codec.TEMP_TYPE2)
_BIT_TABLES = (Table.COIL, Table.DISCRETE_INPUT)
_UNSUPPORTED_ZERO = range(15, 21)  # input registers where 0 means unsupported
_EXTENDED_HEADING = "== Extended blocks (outside the vendor's allowed first addresses; unverified) =="
_ESTIMATE_NOTE = " (estimated: current x PFC voltage)"


class _Raw:
    """Raw values by (table, address); a block that is not ok contributes nothing."""

    def __init__(self, run: ProbeRun) -> None:
        self._values: dict[tuple[Table, int], int] = {}
        self.blocks: dict[tuple[Table, int], BlockResult] = {}
        for result in run.results:
            self.blocks[(result.spec.table, result.spec.start)] = result
            if result.outcome is Outcome.OK and result.values is not None:
                for offset, value in enumerate(result.values):
                    self._values[(result.spec.table, result.spec.start + offset)] = value

    def get(self, table: Table, address: int) -> int | None:
        return self._values.get((table, address))


def _mode_name(register: Register, raw: int) -> str | None:
    enum = {"operating_mode": OperatingMode, "power_mode": PowerMode}.get(register.key)
    if enum is None:
        return None
    try:
        return enum(raw).name.lower().replace("_", " ")
    except ValueError:
        return "unknown"


def _decoded_text(register: Register, raw: int) -> str:
    name = _mode_name(register, raw)
    if name is not None:
        return name
    value = decode(register, raw)
    match register.codec:
        case Codec.BOOL:
            return "on" if value else "off"
        case Codec.TEMP_TYPE1 | Codec.TEMP_TYPE2:
            return f"{value:.1f} °C"
        case Codec.DECI:
            return f"{value:.1f} {register.unit}".rstrip()
        case _:
            return f"{raw} {register.unit}" if register.unit else ""


def _suspect_reason(register: Register, raw: int) -> str | None:
    if register.table is Table.INPUT and register.address in _UNSUPPORTED_ZERO and raw == 0:
        return "0 means unsupported"
    if register.raw_min is not None and register.raw_max is not None:
        if not register.raw_min <= raw <= register.raw_max:
            return "outside raw range"
        if (raw - register.raw_min) % register.raw_step:
            return "off raw step"
    if register.codec in _TEMP_CODECS and not -40 <= decode(register, raw) <= 120:
        return "implausible temperature"
    return None


def _value_text(register: Register, raw: int) -> str:
    """`raw N  decoded` with a SUSPECT suffix when it applies."""
    text = f"raw {raw}"
    decoded = _decoded_text(register, raw)
    if decoded:
        text += f"  {decoded}"
    reason = _suspect_reason(register, raw)
    if reason:
        text += f" SUSPECT ({reason})"
    return text


def _registers_at(table: Table) -> dict[int, Register]:
    return {r.address: r for r in by_table(table)}


def _block_label(result: BlockResult) -> str:
    spec = result.spec
    where = f"{spec.table.value} {spec.start}-{spec.start + spec.count - 1}"
    match result.outcome:
        case Outcome.OK:
            return f"[ok] {where}"
        case Outcome.REFUSED:
            return f"[refused: exception 0x{result.exception_code:02X}] {where}"
        case Outcome.FAILED:
            reason = result.reason.value.replace("_", " ") if result.reason else "unknown"
            if result.reason is FailReason.GATEWAY_EXCEPTION and result.exception_code is not None:
                reason += f" (exception 0x{result.exception_code:02X})"
            return f"[failed: {reason}] {where}"
        case _:
            return f"[not attempted] {where}"


def _block_lines(result: BlockResult) -> list[str]:
    lines = [_block_label(result)]
    if result.outcome is not Outcome.OK or result.values is None:
        return lines
    spec = result.spec
    if spec.table in _BIT_TABLES:
        groups = ["".join(str(v) for v in result.values[i : i + 8]) for i in range(0, len(result.values), 8)]
        lines.append("  raw bits: " + " ".join(groups))
        if spec.table is Table.DISCRETE_INPUT and spec.start == FAULT_BLOCK_START:
            lines.append("  see Active faults")
            return lines
        known = _registers_at(spec.table)
        other: list[int] = []
        for offset, value in enumerate(result.values):
            address = spec.start + offset
            register = known.get(address)
            if register is not None:
                lines.append(_register_line(register, value))
            elif value:
                other.append(address)
        lines.append("  other bits set: " + (", ".join(str(a) for a in other) if other else "none"))
        return lines
    known = _registers_at(spec.table)
    for offset, value in enumerate(result.values):
        address = spec.start + offset
        register = known.get(address)
        lines.append(_register_line(register, value) if register else f"  {address}  -  raw {value}")
    return lines


def _register_line(register: Register, raw: int) -> str:
    line = f"  {register.address}  {register.key}  {register.name}  {_value_text(register, raw)}"
    if register.notes:
        line += f"  ({register.notes})"
    return line


def _summary_line(label: str, register: Register, raw: int | None) -> str:
    return f"{label}  " + ("unavailable" if raw is None else _value_text(register, raw))


def _summary(run: ProbeRun, raw: _Raw) -> list[str]:
    def line(key: str, label: str | None = None) -> str:
        register = get(key)
        return _summary_line(label or key, register, raw.get(register.table, register.address))

    lines = [line("power", "power (coil 0)"), line("running", "running (discrete input 0)")]
    lines += [line("operating_mode"), line("power_mode")]
    mode = raw.get(Table.HOLDING, get("operating_mode").address)
    keys = [_SETPOINT_BY_MODE[mode]] if mode in _SETPOINT_BY_MODE else list(_SETPOINT_BY_MODE.values())
    lines += [line(k) for k in keys]
    lines += [line("inlet_temp"), line("outlet_temp"), line("ambient_temp")]

    current, voltage = get("compressor_current"), get("pfc_voltage")
    raw_current, raw_voltage = raw.get(Table.INPUT, current.address), raw.get(Table.INPUT, voltage.address)
    if raw_current is None or raw_voltage is None:
        lines.append("estimated compressor power  unavailable")
    else:
        watts = decode(current, raw_current) * decode(voltage, raw_voltage)
        lines.append(f"estimated compressor power  {round(watts)} W{_ESTIMATE_NOTE}")
    return lines


def _faults(raw: _Raw) -> list[str]:
    block = raw.blocks.get((Table.DISCRETE_INPUT, FAULT_BLOCK_START))
    if block is None or block.outcome is not Outcome.OK or block.values is None:
        return ["unavailable"]
    faults = decode_faults([bool(v) for v in block.values])
    if not faults:
        return ["none"]
    return [f"{f.code}  {f.kind.value}  {f.description}" for f in faults]


def _printable(byte: int) -> str:
    return chr(byte) if 0x20 <= byte <= 0x7E else "."


def _ascii_line(label: str, raw: _Raw, first: int, last: int) -> str:
    values = [raw.get(Table.INPUT, a) for a in range(first, last + 1)]
    low = "".join("?" if v is None else _printable(v & 0xFF) for v in values)
    two = "".join("??" if v is None else _printable(v >> 8 & 0xFF) + _printable(v & 0xFF) for v in values)
    return f'{label} (unverified)  low byte: "{low}"  two bytes: "{two}"'


def _unverified_raw_line(label: str, raw: _Raw, address: int) -> str:
    value = raw.get(Table.INPUT, address)
    return f"{label} (unverified)  " + ("unavailable" if value is None else f"raw {value}")


def _counts(results: list[BlockResult]) -> str:
    def n(outcome: Outcome) -> int:
        return sum(1 for r in results if r.outcome is outcome)

    return (
        f"{n(Outcome.OK)} ok, {n(Outcome.REFUSED)} refused, {n(Outcome.FAILED)} failed, "
        f"{n(Outcome.NOT_ATTEMPTED)} not attempted"
    )


def render_report(run: ProbeRun) -> str:
    raw = _Raw(run)
    standard = [r for r in run.results if not r.spec.extended]
    extended = [r for r in run.results if r.spec.extended]

    out = ["== Summary: compare with the pump display =="]
    out += _summary(run, raw)
    out += ["", "== Active faults =="]
    out += _faults(raw)
    out += ["", "== Standard blocks =="]
    for result in standard:
        out += _block_lines(result)

    if run.extended:
        out += ["", _EXTENDED_HEADING]
        for result in extended:
            out += _block_lines(result)
        out.append(_ascii_line("board version", raw, 21, 25))
        out.append(_ascii_line("model code", raw, 26, 29))
        out.append(_unverified_raw_line("supply voltage", raw, 30))
        out.append(_unverified_raw_line("compressor restart delay s", raw, 31))

    out += ["", "== Result =="]
    out.append(f"standard: {_counts(standard)}")
    if run.extended:
        out.append(f"extended: {_counts(extended)}")
    out.append(f"run ended: {_RUN_END_TEXT[run.end]}")
    return "\n".join(out) + "\n"


def build_transcript(run: ProbeRun, *, port: int, unit_id: int, timeout_s: float, probe_version: str) -> dict[str, Any]:
    """The JSON-serialisable transcript. It never contains the gateway host."""
    return {
        "format_version": TRANSCRIPT_FORMAT_VERSION,
        "probe_version": probe_version,
        "started_utc": run.started_utc.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "port": port,
        "unit_id": unit_id,
        "timeout_s": timeout_s,
        "extended": run.extended,
        "run_end": run.end.value,
        "blocks": [
            {
                "table": r.spec.table.value,
                "start": r.spec.start,
                "count": r.spec.count,
                "extended": r.spec.extended,
                "outcome": r.outcome.value,
                "reason": r.reason.value if r.reason else None,
                "exception_code": r.exception_code,
                "values": list(r.values) if r.outcome is Outcome.OK and r.values is not None else None,
            }
            for r in run.results
        ],
    }

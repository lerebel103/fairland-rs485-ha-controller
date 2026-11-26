"""Render the register tables in docs/modbus-map.md from app/modbus/registers.py.

Usage:
    uv run python scripts/render_modbus_map.py          # rewrite the generated blocks
    uv run python scripts/render_modbus_map.py --check  # exit 1 if the doc is stale
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.modbus.codec import decode  # noqa: E402
from app.modbus.faults import FAULTS  # noqa: E402
from app.modbus.registers import (  # noqa: E402
    READ_BLOCK_SIZE,
    READ_FUNCTION_CODE,
    STANDARD_BLOCK_STARTS,
    Codec,
    Register,
    Table,
    by_table,
)

DOC = ROOT / "docs" / "modbus-map.md"

_CODEC_LABEL = {
    Codec.BOOL: "bit",
    Codec.RAW: "raw",
    Codec.TEMP_TYPE1: "temp type 1",
    Codec.TEMP_TYPE2: "temp type 2",
    Codec.DECI: "raw / 10",
}


def _range(register: Register) -> str:
    if register.raw_min is None or register.raw_max is None:
        return ""
    text = f"{register.raw_min}–{register.raw_max}"
    if register.codec is not Codec.RAW:
        text += f" ({decode(register, register.raw_min):g}–{decode(register, register.raw_max):g})"
    if register.raw_step != 1:
        text += f", step {register.raw_step}"
    return text


def _write(register: Register) -> str:
    if register.app_writable:
        return "app"
    return "device only" if register.device_writable else "—"


def render_table(table: Table) -> str:
    lines = [
        "| Addr | Key | Name | Decode | Unit | Raw range (decoded) | Write | Evidence | Notes |",
        "|---:|---|---|---|---|---|---|---|---|",
    ]
    for r in by_table(table):
        lines.append(
            f"| {r.address} | `{r.key}` | {r.name} | {_CODEC_LABEL[r.codec]} | {r.unit} | {_range(r)} "
            f"| {_write(r)} | {r.evidence.value} | {r.notes} |"
        )
    return "\n".join(lines)


def render_faults() -> str:
    lines = ["| Addr | Code | Kind | Description |", "|---:|---|---|---|"]
    lines += [f"| {f.address} | {f.code} | {f.kind.value} | {f.description} |" for f in FAULTS.values()]
    return "\n".join(lines)


_READ_BLOCK_ORDER = (Table.COIL, Table.DISCRETE_INPUT, Table.HOLDING, Table.INPUT)


def render_read_blocks() -> str:
    lines = [
        "| Table | Read function | Count | Allowed first addresses (vendor) |",
        "|---|---|---:|---|",
    ]
    for table in _READ_BLOCK_ORDER:
        starts = ", ".join(str(a) for a in STANDARD_BLOCK_STARTS[table])
        lines.append(f"| {table.value} | {READ_FUNCTION_CODE[table]:02d} | {READ_BLOCK_SIZE[table]} | {starts} |")
    return "\n".join(lines)


def blocks() -> dict[str, str]:
    rendered = {table.value: render_table(table) for table in Table}
    rendered["faults"] = render_faults()
    rendered["read_blocks"] = render_read_blocks()
    return rendered


def render(text: str) -> str:
    """Return *text* with every generated block replaced by its current rendering."""
    for name, body in blocks().items():
        pattern = re.compile(rf"(<!-- BEGIN GENERATED: {name} -->\n)(?:.*?\n)?(<!-- END GENERATED: {name} -->)", re.S)
        if not pattern.search(text):
            raise SystemExit(f"marker for generated block '{name}' not found in {DOC}")
        text = pattern.sub(lambda m, body=body: m.group(1) + body + "\n" + m.group(2), text)
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="do not write; exit 1 if the doc is stale")
    args = parser.parse_args(argv)

    current = DOC.read_text()
    updated = render(current)
    if args.check:
        if current != updated:
            print(f"{DOC.relative_to(ROOT)} is stale. Run: make modbus-map", file=sys.stderr)
            return 1
        return 0
    DOC.write_text(updated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

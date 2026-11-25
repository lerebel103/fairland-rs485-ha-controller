"""Fault and protection codes carried in discrete inputs 48-95.

Codes follow the vendor Modbus protocol for the MWH216 / MWH298 boards.
Descriptions follow the Fairland user manual failure-code table, as collected by
the community projects listed in `docs/modbus-map.md`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

FAULT_BLOCK_START = 48
FAULT_BLOCK_SIZE = 48


class FaultKind(StrEnum):
    FAILURE = "failure"
    PROTECTION = "protection"  # the unit is protecting itself; not a device failure


@dataclass(frozen=True, slots=True)
class Fault:
    address: int
    code: str
    description: str
    kind: FaultKind = FaultKind.FAILURE


_P = FaultKind.PROTECTION

FAULTS: dict[int, Fault] = {
    f.address: f
    for f in (
        Fault(48, "E0", "Unknown code E0"),
        Fault(49, "E1", "High pressure protection"),
        Fault(50, "E2", "Low pressure protection"),
        Fault(51, "E3", "No water flow", _P),
        Fault(52, "E4", "3-phase sequence protection (three-phase units only)"),
        Fault(53, "E5", "Power supply outside operating range", _P),
        Fault(54, "E6", "Insufficient water flow, excessive inlet/outlet temperature difference", _P),
        Fault(55, "E7", "Water outlet temperature too high or too low"),
        Fault(56, "E8", "High exhaust temperature protection"),
        Fault(57, "E9", "Unknown code E9"),
        Fault(58, "EA", "Evaporator overheat protection (cooling mode)"),
        Fault(59, "Eb", "Ambient temperature too high or too low", _P),
        Fault(61, "Ed", "Anti-freezing reminder", _P),
        Fault(64, "P0", "Controller communication failure"),
        Fault(65, "P1", "Water inlet temperature sensor failure"),
        Fault(66, "P2", "Water outlet temperature sensor failure"),
        Fault(67, "P3", "Gas exhaust temperature sensor failure"),
        Fault(68, "P4", "Evaporator coil temperature sensor failure"),
        Fault(69, "P5", "Gas return temperature sensor failure"),
        Fault(70, "P6", "Cooling coil temperature sensor failure"),
        Fault(71, "P7", "Ambient temperature sensor failure"),
        Fault(72, "P8", "Cooling plate sensor failure"),
        Fault(73, "P9", "Current sensor failure"),
        Fault(74, "PA", "Restart memory failure"),
        Fault(80, "F0", "Unknown code F0"),
        Fault(81, "F1", "Compressor drive module failure"),
        Fault(82, "F2", "PFC module failure"),
        Fault(83, "F3", "Compressor start failure"),
        Fault(84, "F4", "Compressor running failure"),
        Fault(85, "F5", "Inverter board over-current protection"),
        Fault(86, "F6", "Inverter board overheat protection"),
        Fault(87, "F7", "Current protection"),
        Fault(88, "F8", "Cooling plate overheat protection"),
        Fault(89, "F9", "Fan motor failure"),
        Fault(90, "FA", "PFC module over-current protection"),
        Fault(91, "Fb", "Power filter board no-power protection"),
    )
}


def decode_faults(bits: Sequence[bool]) -> list[Fault]:
    """Return the active faults from one read of the block starting at address 48.

    A set bit at a reserved address is reported as an unknown fault so that it
    is never silently dropped.
    """
    if len(bits) < FAULT_BLOCK_SIZE:
        raise ValueError(f"expected {FAULT_BLOCK_SIZE} bits, got {len(bits)}")
    active: list[Fault] = []
    for offset in range(FAULT_BLOCK_SIZE):
        if not bits[offset]:
            continue
        address = FAULT_BLOCK_START + offset
        active.append(
            FAULTS.get(address) or Fault(address, f"DI{address}", f"Unknown fault at discrete input {address}")
        )
    return active

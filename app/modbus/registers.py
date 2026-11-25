"""Modbus register map for the Fairland MWH216 / MWH298 control board.

This module is the single source of truth for the map. `docs/modbus-map.md` is
rendered from it (`make modbus-map`) and a test fails when the two drift apart.

Nothing here performs I/O. Provenance of every entry and the open questions for
the TiLAB AXCR21V are recorded in `docs/modbus-map.md`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum


class Table(StrEnum):
    """The four Modbus data tables."""

    COIL = "coil"
    DISCRETE_INPUT = "discrete_input"
    INPUT = "input"
    HOLDING = "holding"


class Codec(StrEnum):
    """How a raw register value maps to an engineering value."""

    BOOL = "bool"
    RAW = "raw"
    TEMP_TYPE1 = "temp_type1"  # degC = (raw - 60) / 2
    TEMP_TYPE2 = "temp_type2"  # degC = raw / 2
    DECI = "deci"  # value = raw / 10


class Evidence(StrEnum):
    """Where an entry comes from. None of it is verified on the AXCR21V yet."""

    VENDOR_FIELD = "vendor+field"  # vendor protocol table, and used by a community implementation
    VENDOR = "vendor"  # vendor protocol table only
    COMMUNITY = "community"  # community implementation only; absent from the vendor table


class OperatingMode(IntEnum):
    """Holding register 0."""

    AUTO = 0
    HEATING = 1
    COOLING = 2


class PowerMode(IntEnum):
    """Holding register 1. The vendor table names 0, 1 and 3; 2 comes from community use."""

    SMART = 0
    SILENCE = 1
    SUPER_SILENCE = 2
    TURBO = 3


READ_FUNCTION_CODE: dict[Table, int] = {
    Table.COIL: 0x01,
    Table.DISCRETE_INPUT: 0x02,
    Table.HOLDING: 0x03,
    Table.INPUT: 0x04,
}

WRITE_FUNCTION_CODE: dict[Table, int] = {
    Table.COIL: 0x05,
    Table.HOLDING: 0x06,
}

# Vendor rule: a read must start on an allowed first address and use a fixed count
# (48 for coils and discrete inputs, 3 for input and holding registers). Any other
# shape "may return incorrect data".
READ_BLOCK_SIZE: dict[Table, int] = {
    Table.COIL: 48,
    Table.DISCRETE_INPUT: 48,
    Table.INPUT: 3,
    Table.HOLDING: 3,
}

# Vendor rule: at least 60 ms between two requests from the master.
MIN_REQUEST_GAP_S = 0.06

DEFAULT_UNIT_ID = 1


@dataclass(frozen=True, slots=True)
class Register:
    """One addressable point in the map."""

    key: str
    table: Table
    address: int
    name: str
    codec: Codec = Codec.RAW
    unit: str = ""
    raw_min: int | None = None
    raw_max: int | None = None
    raw_step: int = 1
    device_writable: bool = False
    app_writable: bool = False
    evidence: Evidence = Evidence.VENDOR
    notes: str = ""

    def __post_init__(self) -> None:
        if self.address < 0:
            raise ValueError(f"{self.key}: negative address")
        if self.device_writable and self.table not in WRITE_FUNCTION_CODE:
            raise ValueError(f"{self.key}: {self.table} is a read-only table")
        if self.app_writable and not self.device_writable:
            raise ValueError(f"{self.key}: app_writable requires device_writable")
        if self.app_writable and self.table is Table.HOLDING and (self.raw_min is None or self.raw_max is None):
            raise ValueError(f"{self.key}: an app-writable holding register needs a raw range")
        if self.table in (Table.COIL, Table.DISCRETE_INPUT) and self.codec is not Codec.BOOL:
            raise ValueError(f"{self.key}: bit tables use the bool codec")

    @property
    def block_start(self) -> int:
        """First address of the fixed-size read block that contains this register."""
        size = READ_BLOCK_SIZE[self.table]
        return self.address - self.address % size


def _coil(key: str, address: int, name: str, **kw) -> Register:
    return Register(key, Table.COIL, address, name, codec=Codec.BOOL, device_writable=True, **kw)


def _di(key: str, address: int, name: str, **kw) -> Register:
    return Register(key, Table.DISCRETE_INPUT, address, name, codec=Codec.BOOL, **kw)


def _hr(key: str, address: int, name: str, raw_min: int, raw_max: int, **kw) -> Register:
    return Register(key, Table.HOLDING, address, name, raw_min=raw_min, raw_max=raw_max, device_writable=True, **kw)


def _ir(key: str, address: int, name: str, **kw) -> Register:
    return Register(key, Table.INPUT, address, name, **kw)


_FIELD = Evidence.VENDOR_FIELD
_T1 = Codec.TEMP_TYPE1
_T2 = Codec.TEMP_TYPE2

REGISTERS: tuple[Register, ...] = (
    # ---- Coils (read 0x01, write 0x05) ----
    _coil("power", 0, "Power switch", app_writable=True, evidence=_FIELD),
    _coil("forced_defrost", 1, "Compulsory defrosting", notes="Write 1 to enter. Not written by the app."),
    _coil(
        "factory_reset",
        2,
        "Restore factory values",
        notes="Marked reserved by the vendor. Never write.",
    ),
    # ---- Discrete inputs (read 0x02) ----
    _di("running", 0, "On/off state", evidence=_FIELD),
    _di("defrosting", 1, "Defrosting"),
    _di("din1", 2, "Digital input DIN1", notes="Function unverified."),
    _di("din2", 3, "Digital input DIN2", notes="Function unverified."),
    _di("din3", 4, "Digital input DIN3", notes="Function unverified."),
    _di("din4", 5, "Digital input DIN4", notes="Function unverified."),
    _di("din5", 6, "Digital input DIN5", notes="Function unverified."),
    _di("out1", 7, "Output OUT1", notes="Function unverified."),
    _di("out2", 8, "Output OUT2", notes="Function unverified."),
    _di("out3", 9, "Output OUT3", notes="Function unverified."),
    _di("out4", 10, "Output OUT4", notes="Function unverified."),
    _di("out5", 11, "Output OUT5", notes="Function unverified."),
    _di("out6", 12, "Output OUT6", notes="Function unverified."),
    _di("out7", 13, "Output OUT7", notes="Function unverified."),
    _di("out8", 14, "Output OUT8", notes="Function unverified."),
    _di("out9", 15, "Output OUT9", notes="Function unverified."),
    _di(
        "fault_indicator",
        16,
        "Malfunction / protection indicator",
        evidence=_FIELD,
        notes="Some boards leave this at 0; combine with the fault block (48-95).",
    ),
    _di("compressor_demand", 17, "Compressor running demand"),
    # ---- Holding registers (read 0x03, write 0x06) ----
    _hr(
        "operating_mode",
        0,
        "Function selection",
        0,
        2,
        app_writable=True,
        evidence=_FIELD,
        notes="0 auto, 1 heating, 2 cooling.",
    ),
    _hr(
        "power_mode",
        1,
        "Working mode selection",
        0,
        3,
        app_writable=True,
        evidence=_FIELD,
        notes="0 smart, 1 silence, 2 super silence (community), 3 turbo (not on all models).",
    ),
    _hr(
        "target_temp_auto",
        2,
        "Auto mode target temperature",
        84,
        140,
        raw_step=2,
        codec=_T1,
        unit="°C",
        app_writable=True,
        evidence=_FIELD,
    ),  # fmt: skip
    _hr(
        "target_temp_heating",
        3,
        "Heating mode target temperature",
        96,
        140,
        raw_step=2,
        codec=_T1,
        unit="°C",
        app_writable=True,
        evidence=_FIELD,
    ),  # fmt: skip
    _hr(
        "target_temp_cooling",
        4,
        "Cooling mode target temperature",
        84,
        120,
        raw_step=2,
        codec=_T1,
        unit="°C",
        app_writable=True,
        evidence=_FIELD,
    ),  # fmt: skip
    _hr(
        "pump_mode",
        5,
        "Water pump working mode (P0)",
        0,
        2,
        notes="0 continuous, 1 water temperature control, 2 time / water temperature control.",
    ),  # fmt: skip
    _hr("pump_time", 6, "Water pump working time (P1)", 10, 120, raw_step=5, unit="min"),
    _hr("defrost_interval", 7, "Compressor run time before defrost", 30, 90, unit="min"),
    _hr("defrost_entry_temp", 8, "Defrost entry temperature (P3)", 26, 60, raw_step=2, codec=_T1, unit="°C"),
    _hr("defrost_max_time", 9, "Maximum defrost run time (P4)", 1, 12, unit="min"),
    _hr("defrost_exit_temp", 10, "Defrost exit temperature (P5)", 76, 120, raw_step=2, codec=_T1, unit="°C"),
    _hr("eev_superheat_heating", 17, "Expansion valve superheat, heating", 40, 100, raw_step=2, codec=_T1, unit="°C"),
    _hr("eev_superheat_cooling", 18, "Expansion valve superheat, cooling", 40, 100, raw_step=2, codec=_T1, unit="°C"),
    _hr("power_off_memory", 25, "Power-off restart memory", 0, 1, notes="1 restores the pre-power-down state."),
    # ---- Input registers (read 0x04) ----
    _ir("compressor_speed_pct", 0, "Compressor running speed", unit="%", evidence=_FIELD),
    _ir("compressor_target_freq", 1, "Compressor target frequency", unit="Hz"),
    _ir("pfc_voltage", 2, "PFC voltage", unit="V", evidence=_FIELD),
    _ir("inlet_temp", 3, "Water inlet temperature (AIN1)", codec=_T1, unit="°C", evidence=_FIELD),
    _ir("outlet_temp", 4, "Water outlet temperature (AIN2)", codec=_T1, unit="°C", evidence=_FIELD),
    _ir("ambient_temp", 5, "Ambient temperature (AIN7)", codec=_T1, unit="°C", evidence=_FIELD),
    _ir("exhaust_temp", 6, "Gas exhaust temperature (AIN5)", codec=_T2, unit="°C"),
    _ir("evaporator_coil_temp", 7, "Outer coil temperature, evaporator (AIN3)", codec=_T1, unit="°C"),
    _ir("suction_temp", 8, "Gas return temperature (AIN6)", codec=_T1, unit="°C"),
    _ir(
        "exchanger_coil_temp", 9, "Inner coil temperature, heat exchanger (AIN4)", codec=_T1, unit="°C", evidence=_FIELD
    ),  # fmt: skip
    _ir("compressor_freq", 10, "Compressor frequency", unit="Hz", evidence=_FIELD),
    _ir("compressor_current", 11, "Compressor current", codec=Codec.DECI, unit="A", evidence=_FIELD),
    _ir("cooling_plate_temp", 12, "Cooling plate temperature", codec=_T2, unit="°C"),
    _ir("eev_opening", 13, "Expansion valve opening"),
    _ir("fan_speed", 14, "DC fan motor speed", unit="RPM"),
    _ir(
        "auto_temp_min",
        15,
        "Auto setpoint lower limit",
        codec=_T1,
        unit="°C",
        evidence=Evidence.COMMUNITY,
        notes="InverX only; reads 0 where unsupported.",
    ),  # fmt: skip
    _ir(
        "auto_temp_max",
        16,
        "Auto setpoint upper limit",
        codec=_T1,
        unit="°C",
        evidence=Evidence.COMMUNITY,
        notes="InverX only; reads 0 where unsupported.",
    ),  # fmt: skip
    _ir(
        "heating_temp_min",
        17,
        "Heating setpoint lower limit",
        codec=_T1,
        unit="°C",
        evidence=Evidence.COMMUNITY,
        notes="InverX only; reads 0 where unsupported.",
    ),  # fmt: skip
    _ir(
        "heating_temp_max",
        18,
        "Heating setpoint upper limit",
        codec=_T1,
        unit="°C",
        evidence=Evidence.COMMUNITY,
        notes="InverX only; reads 0 where unsupported.",
    ),  # fmt: skip
    _ir(
        "cooling_temp_min",
        19,
        "Cooling setpoint lower limit",
        codec=_T1,
        unit="°C",
        evidence=Evidence.COMMUNITY,
        notes="InverX only; reads 0 where unsupported.",
    ),  # fmt: skip
    _ir(
        "cooling_temp_max",
        20,
        "Cooling setpoint upper limit",
        codec=_T1,
        unit="°C",
        evidence=Evidence.COMMUNITY,
        notes="InverX only; reads 0 where unsupported.",
    ),  # fmt: skip
)

BY_KEY: dict[str, Register] = {r.key: r for r in REGISTERS}

# The complete set of points the app may ever write. Changing it needs an approved spec.
APP_WRITABLE_KEYS: frozenset[str] = frozenset(r.key for r in REGISTERS if r.app_writable)


def get(key: str) -> Register:
    """Return the register with this key, or raise KeyError."""
    return BY_KEY[key]


def by_table(table: Table) -> tuple[Register, ...]:
    """All registers of one table, in address order."""
    return tuple(sorted((r for r in REGISTERS if r.table is table), key=lambda r: r.address))

"""Pure conversions between raw register values and engineering values."""

from __future__ import annotations

from app.modbus.registers import Codec, Register


def decode(register: Register, raw: int | bool) -> float | int | bool:
    """Convert a raw value read from the device into its engineering value."""
    match register.codec:
        case Codec.BOOL:
            return bool(raw)
        case Codec.TEMP_TYPE1:
            return (int(raw) - 60) / 2
        case Codec.TEMP_TYPE2:
            return int(raw) / 2
        case Codec.DECI:
            return int(raw) / 10
        case Codec.RAW:
            return int(raw)
    raise ValueError(f"{register.key}: unsupported codec {register.codec}")


def encode(register: Register, value: float | int | bool) -> int:
    """Convert an engineering value into the raw value to write.

    Raises PermissionError when the app is not allowed to write the register and
    ValueError when the value is outside the register's range or off its step.
    """
    if not register.app_writable:
        raise PermissionError(f"{register.key}: not on the app write allowlist")

    match register.codec:
        case Codec.BOOL:
            if not isinstance(value, bool):
                raise ValueError(f"{register.key}: expected a bool, got {value!r}")
            return int(value)
        case Codec.TEMP_TYPE1:
            scaled = float(value) * 2 + 60
        case Codec.RAW:
            scaled = float(value)
        case _:
            raise ValueError(f"{register.key}: codec {register.codec} is read-only")

    raw = round(scaled)
    if raw != scaled:
        raise ValueError(f"{register.key}: {value!r} is finer than the register resolution")
    if register.raw_min is None or register.raw_max is None:
        raise ValueError(f"{register.key}: no raw range defined")
    if not register.raw_min <= raw <= register.raw_max:
        low, high = decode(register, register.raw_min), decode(register, register.raw_max)
        raise ValueError(f"{register.key}: {value!r} is outside {low}..{high}")
    if (raw - register.raw_min) % register.raw_step:
        raise ValueError(f"{register.key}: {value!r} is off the register step")
    return raw

"""Tests for raw <-> engineering value conversion."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.modbus.codec import decode, encode
from app.modbus.registers import get


@pytest.mark.parametrize(
    ("key", "raw", "expected"),
    [
        ("inlet_temp", 120, 30.0),  # vendor sample for temperature type 1
        ("inlet_temp", 60, 0.0),
        ("ambient_temp", 51, -4.5),
        ("exhaust_temp", 120, 60.0),  # vendor sample for temperature type 2
        ("compressor_current", 53, 5.3),
        ("pfc_voltage", 380, 380),
        ("running", 1, True),
        ("running", 0, False),
    ],
)
def test_decode(key, raw, expected):
    assert decode(get(key), raw) == expected


@pytest.mark.parametrize(
    ("key", "value", "raw"),
    [
        ("power", True, 1),
        ("power", False, 0),
        ("operating_mode", 1, 1),
        ("power_mode", 2, 2),
        ("target_temp_heating", 26, 112),  # vendor default
        ("target_temp_heating", 18, 96),
        ("target_temp_heating", 40, 140),
        ("target_temp_cooling", 12, 84),
        ("target_temp_cooling", 30, 120),
    ],
)
def test_encode(key, value, raw):
    assert encode(get(key), value) == raw


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("target_temp_heating", 17),  # below range
        ("target_temp_heating", 41),  # above range
        ("target_temp_cooling", 31),
        ("target_temp_heating", 26.5),  # off the 1 degC step
        ("target_temp_heating", 26.25),  # finer than the register resolution
        ("operating_mode", 3),
        ("power_mode", -1),
        ("power", 1),  # coils take a bool, not an int
    ],
)
def test_encode_rejects_invalid_values(key, value):
    with pytest.raises(ValueError):
        encode(get(key), value)


@pytest.mark.parametrize("key", ["forced_defrost", "factory_reset", "pump_mode", "defrost_exit_temp", "inlet_temp"])
def test_encode_refuses_points_off_the_allowlist(key):
    with pytest.raises(PermissionError):
        encode(get(key), 1)


@pytest.mark.parametrize("key", ["target_temp_auto", "target_temp_heating", "target_temp_cooling"])
@given(data=st.data())
def test_setpoint_round_trip(key, data):
    register = get(key)
    raw = data.draw(st.integers(register.raw_min, register.raw_max).filter(lambda r: (r - register.raw_min) % 2 == 0))
    assert encode(register, decode(register, raw)) == raw

"""Tests for the register map invariants."""

from collections import Counter

import pytest

from app.modbus.registers import (
    APP_WRITABLE_KEYS,
    READ_BLOCK_SIZE,
    REGISTERS,
    Codec,
    OperatingMode,
    PowerMode,
    Register,
    Table,
    by_table,
    get,
)


def test_keys_are_unique():
    assert [k for k, n in Counter(r.key for r in REGISTERS).items() if n > 1] == []


def test_addresses_are_unique_per_table():
    assert [k for k, n in Counter((r.table, r.address) for r in REGISTERS).items() if n > 1] == []


def test_app_write_allowlist_is_pinned():
    """Widening this set needs an approved spec; see docs/modbus-map.md (Write policy)."""
    assert APP_WRITABLE_KEYS == {
        "power",
        "operating_mode",
        "power_mode",
        "target_temp_auto",
        "target_temp_heating",
        "target_temp_cooling",
    }


@pytest.mark.parametrize("key", ["forced_defrost", "factory_reset", "pump_mode", "eev_superheat_heating"])
def test_service_points_are_never_app_writable(key):
    assert get(key).device_writable
    assert not get(key).app_writable


def test_read_only_tables_have_no_writable_points():
    for table in (Table.DISCRETE_INPUT, Table.INPUT):
        assert not any(r.device_writable for r in by_table(table))


@pytest.mark.parametrize(
    ("key", "block_start"),
    [
        ("power", 0),
        ("fault_indicator", 0),
        ("operating_mode", 0),
        ("target_temp_auto", 0),
        ("target_temp_heating", 3),
        ("target_temp_cooling", 3),
        ("power_off_memory", 24),
        ("pfc_voltage", 0),
        ("ambient_temp", 3),
        ("compressor_current", 9),
        ("fan_speed", 12),
        ("cooling_temp_max", 18),
    ],
)
def test_block_start(key, block_start):
    assert get(key).block_start == block_start


def test_block_sizes_follow_vendor_rule():
    assert READ_BLOCK_SIZE == {Table.COIL: 48, Table.DISCRETE_INPUT: 48, Table.INPUT: 3, Table.HOLDING: 3}


def test_by_table_is_sorted_by_address():
    for table in Table:
        addresses = [r.address for r in by_table(table)]
        assert addresses == sorted(addresses)


def test_mode_enums_fit_their_register_ranges():
    mode, power = get("operating_mode"), get("power_mode")
    assert {m.value for m in OperatingMode} == set(range(mode.raw_min, mode.raw_max + 1))
    assert {m.value for m in PowerMode} == set(range(power.raw_min, power.raw_max + 1))


def test_get_unknown_key_raises():
    with pytest.raises(KeyError):
        get("nope")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"table": Table.INPUT, "device_writable": True},
        {"table": Table.HOLDING, "app_writable": True},
        {"table": Table.HOLDING, "device_writable": True, "app_writable": True},
        {"table": Table.COIL, "codec": Codec.RAW},
        {"table": Table.HOLDING, "address": -1},
    ],
)
def test_invalid_definitions_are_rejected(kwargs):
    base = {"key": "x", "table": Table.HOLDING, "address": 0, "name": "x"}
    with pytest.raises(ValueError):
        Register(**(base | kwargs))


def test_standard_block_starts_are_the_vendor_list():
    from app.modbus.registers import STANDARD_BLOCK_STARTS

    assert STANDARD_BLOCK_STARTS == {
        Table.COIL: (0,),
        Table.DISCRETE_INPUT: (0, 48),
        Table.HOLDING: (0, 3, 6, 9, 12, 15, 18),
        Table.INPUT: (0, 3, 6, 9, 12),
    }


def test_standard_block_starts_are_multiples_of_the_block_size():
    from app.modbus.registers import STANDARD_BLOCK_STARTS

    for table, starts in STANDARD_BLOCK_STARTS.items():
        assert all(start % READ_BLOCK_SIZE[table] == 0 for start in starts)

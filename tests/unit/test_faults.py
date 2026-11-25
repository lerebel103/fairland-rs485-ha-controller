"""Tests for fault block decoding."""

import pytest

from app.modbus.faults import FAULT_BLOCK_SIZE, FAULT_BLOCK_START, FAULTS, FaultKind, decode_faults


def _bits(*addresses: int) -> list[bool]:
    bits = [False] * FAULT_BLOCK_SIZE
    for address in addresses:
        bits[address - FAULT_BLOCK_START] = True
    return bits


def test_no_faults():
    assert decode_faults(_bits()) == []


def test_known_faults_in_address_order():
    assert [f.code for f in decode_faults(_bits(81, 51))] == ["E3", "F1"]


def test_protection_codes():
    assert {f.code for f in FAULTS.values() if f.kind is FaultKind.PROTECTION} == {"E3", "E5", "E6", "Eb", "Ed"}


def test_reserved_bit_is_reported_not_dropped():
    (fault,) = decode_faults(_bits(60))
    assert fault.address == 60
    assert "Unknown" in fault.description


def test_all_faults_lie_inside_the_block():
    assert all(FAULT_BLOCK_START <= a < FAULT_BLOCK_START + FAULT_BLOCK_SIZE for a in FAULTS)


def test_short_read_is_rejected():
    with pytest.raises(ValueError):
        decode_faults([False] * 8)

"""ReadOnlyLink and open_client (spec 001, tasks 2-4)."""

import asyncio

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pymodbus.exceptions import ModbusException

from app.modbus import readonly_link
from app.modbus.readonly_link import (
    QUIET_AFTER_FAILURE_S,
    READ_METHODS,
    BlockResult,
    BlockSpec,
    FailReason,
    Outcome,
    ReadOnlyLink,
    open_client,
)
from app.modbus.registers import READ_BLOCK_SIZE, STANDARD_BLOCK_STARTS, Table
from tests.unit.fakes import FakeClient, FakeClock, bits, error, lost, no_reply, registers

ALL_SPECS = frozenset(BlockSpec(t, s) for t, starts in STANDARD_BLOCK_STARTS.items() for s in starts)


def make(*actions, unit_id=1):
    clock = FakeClock()
    client = FakeClient(clock, list(actions))
    link = ReadOnlyLink(client, unit_id=unit_id, allowed=ALL_SPECS, sleep=clock.sleep, monotonic=clock.monotonic)
    return clock, client, link


def test_read_methods_are_exactly_the_four_reads():
    assert set(READ_METHODS.values()) == {
        "read_coils",
        "read_discrete_inputs",
        "read_holding_registers",
        "read_input_registers",
    }


async def test_bit_block_ok_is_cut_to_48_and_zero_one():
    pattern = [i % 3 == 0 for i in range(48)]
    _, client, link = make(bits(pattern))
    result = await link.read_block(BlockSpec(Table.COIL, 0))
    assert result.outcome is Outcome.OK
    assert result.values == tuple(int(b) for b in pattern)
    assert len(result.values) == 48
    assert client.calls[0].method == "read_coils"
    assert (client.calls[0].address, client.calls[0].count, client.calls[0].device_id) == (0, 48, 1)


@pytest.mark.parametrize(
    ("table", "start", "method"),
    [
        (Table.DISCRETE_INPUT, 48, "read_discrete_inputs"),
        (Table.HOLDING, 3, "read_holding_registers"),
        (Table.INPUT, 12, "read_input_registers"),
    ],
)
async def test_each_table_uses_its_read_method(table, start, method):
    action = bits([0] * 48) if table is Table.DISCRETE_INPUT else registers([7, 8, 9])
    _, client, link = make(action, unit_id=5)
    result = await link.read_block(BlockSpec(table, start))
    assert result.outcome is Outcome.OK
    call = client.calls[0]
    assert (call.method, call.address, call.count, call.device_id) == (method, start, READ_BLOCK_SIZE[table], 5)


async def test_register_values_returned():
    _, _, link = make(registers([1, 2, 3]))
    assert (await link.read_block(BlockSpec(Table.HOLDING, 0))).values == (1, 2, 3)


async def test_spacing_and_no_sleep_when_enough_time_passed():
    clock, client, link = make(registers([1, 2, 3]), registers([1, 2, 3]), registers([1, 2, 3]))
    await link.read_block(BlockSpec(Table.HOLDING, 0))
    await link.read_block(BlockSpec(Table.HOLDING, 3))
    assert clock.sleeps and clock.sleeps[0] == pytest.approx(0.06)
    assert client.calls[1].time - client.ends[0] >= 0.06 - 1e-9
    clock.now += 5
    clock.sleeps.clear()
    await link.read_block(BlockSpec(Table.HOLDING, 6))
    assert clock.sleeps == []


async def test_block_outside_allowed_raises_and_client_not_called():
    _, client, link = make()
    with pytest.raises(ValueError):
        await link.read_block(BlockSpec(Table.HOLDING, 1))
    with pytest.raises(ValueError):
        await link.read_block(BlockSpec(Table.HOLDING, 24, extended=True))
    assert client.calls == []


async def test_exception_0x02_is_refused_with_code_and_no_quiet_wait():
    clock, _, link = make(error(0x02))
    result = await link.read_block(BlockSpec(Table.HOLDING, 15))
    assert (result.outcome, result.exception_code, result.values) == (Outcome.REFUSED, 2, None)
    assert clock.sleeps == []


@pytest.mark.parametrize("code", [0x0A, 0x0B])
async def test_gateway_exceptions_are_failed(code):
    clock, _, link = make(error(code))
    result = await link.read_block(BlockSpec(Table.HOLDING, 0))
    assert (result.outcome, result.reason, result.exception_code) == (
        Outcome.FAILED,
        FailReason.GATEWAY_EXCEPTION,
        code,
    )
    assert clock.sleeps == [QUIET_AFTER_FAILURE_S]


async def test_no_reply_is_failed_with_quiet_wait():
    clock, _, link = make(no_reply())
    result = await link.read_block(BlockSpec(Table.INPUT, 0))
    assert (result.outcome, result.reason) == (Outcome.FAILED, FailReason.NO_REPLY)
    assert clock.sleeps == [QUIET_AFTER_FAILURE_S]


async def test_other_modbus_exception_is_no_reply():
    clock = FakeClock()
    client = FakeClient(clock, [])

    async def boom(*a, **k):
        raise ModbusException("odd")

    client.read_input_registers = boom
    link = ReadOnlyLink(client, unit_id=1, allowed=ALL_SPECS, sleep=clock.sleep, monotonic=clock.monotonic)
    result = await link.read_block(BlockSpec(Table.INPUT, 0))
    assert (result.outcome, result.reason) == (Outcome.FAILED, FailReason.NO_REPLY)


async def test_too_few_bits_is_wrong_length():
    clock, _, link = make(bits([0] * 40))
    result = await link.read_block(BlockSpec(Table.COIL, 0))
    assert (result.outcome, result.reason) == (Outcome.FAILED, FailReason.WRONG_LENGTH)
    assert clock.sleeps == [QUIET_AFTER_FAILURE_S]


async def test_wrong_register_count_is_wrong_length():
    _, _, link = make(registers([1, 2]))
    result = await link.read_block(BlockSpec(Table.HOLDING, 0))
    assert (result.outcome, result.reason) == (Outcome.FAILED, FailReason.WRONG_LENGTH)


async def test_connection_exception_is_connection_lost_without_quiet_wait():
    clock, client, link = make(lost())
    result = await link.read_block(BlockSpec(Table.HOLDING, 0))
    assert (result.outcome, result.reason) == (Outcome.FAILED, FailReason.CONNECTION_LOST)
    assert link.connection_lost
    assert clock.sleeps == []
    again = await link.read_block(BlockSpec(Table.HOLDING, 3))
    assert again.reason is FailReason.CONNECTION_LOST
    assert len(client.calls) == 1


async def test_client_not_connected_before_request():
    _, client, link = make(registers([1, 2, 3]))
    client.connected = False
    result = await link.read_block(BlockSpec(Table.HOLDING, 0))
    assert result.reason is FailReason.CONNECTION_LOST
    assert link.connection_lost
    assert client.calls == []


async def test_one_call_per_block_and_close():
    _, client, link = make(no_reply())
    await link.read_block(BlockSpec(Table.HOLDING, 0))
    assert len(client.calls) == 1
    link.close()
    assert client.closed == 1


_ACTIONS = st.sampled_from(["ok", "no_reply", "error2", "error10", "lost", "short"])


def _action(kind, table):
    n = READ_BLOCK_SIZE[table]
    ok = bits([1] * n) if n == 48 else registers([1] * n)
    return {
        "ok": ok,
        "no_reply": no_reply(),
        "error2": error(2),
        "error10": error(10),
        "lost": lost(),
        "short": bits([1] * 3) if n == 48 else registers([1]),
    }[kind]


@given(st.lists(st.tuples(st.sampled_from(sorted(ALL_SPECS, key=lambda s: (s.table, s.start))), _ACTIONS), max_size=20))
def test_property_methods_spacing_and_quiet(steps):
    async def go():
        clock = FakeClock()
        client = FakeClient(clock, [_action(kind, spec.table) for spec, kind in steps])
        link = ReadOnlyLink(client, unit_id=1, allowed=ALL_SPECS, sleep=clock.sleep, monotonic=clock.monotonic)
        sent: list[tuple[BlockSpec, BlockResult]] = []
        for spec, _ in steps:
            before = len(client.calls)
            result = await link.read_block(spec)
            if len(client.calls) > before:
                sent.append((spec, result))
        return client, sent

    client, sent = asyncio.run(go())
    assert len(client.calls) == len(sent)
    assert all(c.method in READ_METHODS.values() for c in client.calls)
    for call, (spec, _) in zip(client.calls, sent, strict=True):
        assert call.count == READ_BLOCK_SIZE[spec.table]
    for i in range(1, len(client.calls)):
        _, previous = sent[i - 1]
        quiet = previous.outcome is Outcome.FAILED and previous.reason is not FailReason.CONNECTION_LOST
        gap = client.calls[i].time - client.ends[i - 1]
        assert gap >= (QUIET_AFTER_FAILURE_S if quiet else 0.06) - 1e-9


# ---- open_client ----


class FakeTcpClient:
    instances: list[FakeTcpClient] = []
    behaviour = "ok"

    def __init__(self, host, **kwargs):
        self.host, self.kwargs, self.closed = host, kwargs, 0
        FakeTcpClient.instances.append(self)

    async def connect(self):
        match FakeTcpClient.behaviour:
            case "ok":
                return True
            case "false":
                return False
            case "raise":
                raise OSError("refused")
            case "hang":
                await asyncio.sleep(10)

    def close(self):
        self.closed += 1


@pytest.fixture
def fake_tcp(monkeypatch):
    FakeTcpClient.instances = []
    FakeTcpClient.behaviour = "ok"
    monkeypatch.setattr(readonly_link, "AsyncModbusTcpClient", FakeTcpClient)
    return FakeTcpClient


async def test_open_client_builds_client_without_retries(fake_tcp):
    client = await open_client("gw.local", 4196, 3.0)
    assert client is fake_tcp.instances[0]
    assert client.host == "gw.local"
    assert client.kwargs == {"port": 4196, "timeout": 3.0, "retries": 0, "reconnect_delay": 0}
    assert client.closed == 0


@pytest.mark.parametrize("behaviour", ["false", "raise", "hang"])
async def test_open_client_failure_closes_and_raises(fake_tcp, behaviour):
    fake_tcp.behaviour = behaviour
    with pytest.raises(ConnectionError):
        await open_client("gw.local", 4196, 0.5 if behaviour != "hang" else 0.01)
    assert fake_tcp.instances[0].closed == 1


async def test_raw_oserror_is_connection_lost_and_later_blocks_not_sent():
    clock = FakeClock()
    client = FakeClient(clock, [])

    async def broken(*a, **k):
        raise BrokenPipeError("pipe")

    client.read_holding_registers = broken
    link = ReadOnlyLink(client, unit_id=1, allowed=ALL_SPECS, sleep=clock.sleep, monotonic=clock.monotonic)
    result = await link.read_block(BlockSpec(Table.HOLDING, 0))
    assert (result.outcome, result.reason) == (Outcome.FAILED, FailReason.CONNECTION_LOST)
    assert link.connection_lost
    assert clock.sleeps == []

"""The one request sender of the read-only probe (spec 001).

`ReadOnlyLink` exposes a single operation, reading a block. It reaches the Modbus
client only through `READ_METHODS`, which holds the four read operations, so no write
can be issued through it. It adds the vendor's request spacing and classifies every
read into an outcome.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusException

from app.modbus.registers import MIN_REQUEST_GAP_S, READ_BLOCK_SIZE, Table

MIN_GAP_S = MIN_REQUEST_GAP_S
QUIET_AFTER_FAILURE_S = 1.0

READ_METHODS: dict[Table, str] = {
    Table.COIL: "read_coils",
    Table.DISCRETE_INPUT: "read_discrete_inputs",
    Table.HOLDING: "read_holding_registers",
    Table.INPUT: "read_input_registers",
}
GATEWAY_EXCEPTION_CODES: frozenset[int] = frozenset({0x0A, 0x0B})
_BIT_TABLES = (Table.COIL, Table.DISCRETE_INPUT)


class Outcome(StrEnum):
    OK = "ok"
    REFUSED = "refused"
    FAILED = "failed"
    NOT_ATTEMPTED = "not_attempted"


class FailReason(StrEnum):
    NO_REPLY = "no_reply"
    GATEWAY_EXCEPTION = "gateway_exception"
    WRONG_LENGTH = "wrong_length"
    CONNECTION_LOST = "connection_lost"


@dataclass(frozen=True, slots=True)
class BlockSpec:
    table: Table
    start: int
    extended: bool = False

    @property
    def count(self) -> int:
        return READ_BLOCK_SIZE[self.table]


@dataclass(frozen=True, slots=True)
class BlockResult:
    spec: BlockSpec
    outcome: Outcome
    values: tuple[int, ...] | None = None  # bits as 0/1; set only when outcome is OK
    reason: FailReason | None = None  # set only when outcome is FAILED
    exception_code: int | None = None  # set for REFUSED and for GATEWAY_EXCEPTION


class ReadClient(Protocol):
    """The part of pymodbus' AsyncModbusTcpClient that the link uses."""

    @property
    def connected(self) -> bool: ...
    async def read_coils(self, address: int, *, count: int, device_id: int) -> Any: ...
    async def read_discrete_inputs(self, address: int, *, count: int, device_id: int) -> Any: ...
    async def read_holding_registers(self, address: int, *, count: int, device_id: int) -> Any: ...
    async def read_input_registers(self, address: int, *, count: int, device_id: int) -> Any: ...
    def close(self) -> None: ...


async def open_client(host: str, port: int, timeout: float) -> ReadClient:
    """Connect once, with pymodbus' automatic retries and reconnection switched off."""
    client = AsyncModbusTcpClient(host, port=port, timeout=timeout, retries=0, reconnect_delay=0)
    try:
        connected = await asyncio.wait_for(client.connect(), timeout)
    except (TimeoutError, OSError, ModbusException) as exc:
        client.close()
        raise ConnectionError(f"could not connect to {host}:{port}") from exc
    except BaseException:
        client.close()
        raise
    if not connected:
        client.close()
        raise ConnectionError(f"could not connect to {host}:{port}")
    return client


class ReadOnlyLink:
    def __init__(
        self,
        client: ReadClient,
        *,
        unit_id: int,
        allowed: frozenset[BlockSpec],
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        should_stop: Callable[[], bool] = lambda: False,
    ) -> None:
        self._client = client
        self._unit_id = unit_id
        self._allowed = allowed
        self._sleep = sleep
        self._monotonic = monotonic
        self._should_stop = should_stop
        self._last_end: float | None = None
        self._connection_lost = False

    @property
    def connection_lost(self) -> bool:
        return self._connection_lost

    def close(self) -> None:
        self._client.close()

    async def read_block(self, spec: BlockSpec) -> BlockResult:
        if spec not in self._allowed:
            raise ValueError(f"block {spec} is not in the allowed set")
        if self._connection_lost or not self._client.connected:
            self._connection_lost = True
            return _failed(spec, FailReason.CONNECTION_LOST)

        if self._last_end is not None:
            remaining = MIN_GAP_S - (self._monotonic() - self._last_end)
            if remaining > 0:
                await self._sleep(remaining)
                if self._should_stop():
                    # Interrupted while waiting: an in-flight request may finish, a new one must not start.
                    return BlockResult(spec, Outcome.NOT_ATTEMPTED)

        result = await self._request(spec)
        self._last_end = self._monotonic()

        if result.outcome is Outcome.FAILED and result.reason is not FailReason.CONNECTION_LOST:
            await self._sleep(QUIET_AFTER_FAILURE_S)
        return result

    async def _request(self, spec: BlockSpec) -> BlockResult:
        method = getattr(self._client, READ_METHODS[spec.table])
        try:
            reply = await method(spec.start, count=spec.count, device_id=self._unit_id)
        except ConnectionException:
            self._connection_lost = True
            return _failed(spec, FailReason.CONNECTION_LOST)
        except ModbusException:
            return _failed(spec, FailReason.NO_REPLY)
        except OSError:
            # A raw socket error from the library: the connection is gone.
            self._connection_lost = True
            return _failed(spec, FailReason.CONNECTION_LOST)

        if reply.isError():
            code = reply.exception_code
            if code in GATEWAY_EXCEPTION_CODES:
                return _failed(spec, FailReason.GATEWAY_EXCEPTION, code)
            return BlockResult(spec, Outcome.REFUSED, exception_code=code)

        if spec.table in _BIT_TABLES:
            if len(reply.bits) < spec.count:
                return _failed(spec, FailReason.WRONG_LENGTH)
            values = tuple(int(bool(b)) for b in reply.bits[: spec.count])
        else:
            if len(reply.registers) != spec.count:
                return _failed(spec, FailReason.WRONG_LENGTH)
            values = tuple(int(r) for r in reply.registers)
        return BlockResult(spec, Outcome.OK, values=values)


def _failed(spec: BlockSpec, reason: FailReason, exception_code: int | None = None) -> BlockResult:
    return BlockResult(spec, Outcome.FAILED, reason=reason, exception_code=exception_code)

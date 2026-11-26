"""Test doubles for the read-only probe: no test opens a socket or really sleeps."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from pymodbus.exceptions import ConnectionException, ModbusIOException

from app.modbus.readonly_link import BlockResult, BlockSpec


class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


@dataclass(frozen=True)
class Action:
    kind: str
    payload: Any = None


def bits(values: list[int | bool]) -> Action:
    return Action("bits", list(values))


def registers(values: list[int]) -> Action:
    return Action("registers", list(values))


def error(code: int) -> Action:
    return Action("error", code)


def no_reply() -> Action:
    return Action("no_reply")


def lost() -> Action:
    return Action("lost")


@dataclass(frozen=True)
class Call:
    method: str
    address: int
    count: int
    device_id: int
    time: float


_MEMBERS = {
    "connected",
    "read_coils",
    "read_discrete_inputs",
    "read_holding_registers",
    "read_input_registers",
    "close",
}


class FakeClient:
    """Implements `ReadClient`. Any other attribute access fails the test."""

    def __init__(
        self,
        clock: FakeClock,
        actions: list[Action] | None = None,
        on_request: Callable[[int], None] | None = None,
    ) -> None:
        self._clock = clock
        self._actions = list(actions or [])
        self._on_request = on_request
        self.calls: list[Call] = []
        self.ends: list[float] = []
        self.closed = 0
        self._connected = True

    def script(self, *actions: Action) -> None:
        self._actions.extend(actions)

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"the link used a client member outside ReadClient: {name}")

    @property
    def connected(self) -> bool:
        return self._connected

    @connected.setter
    def connected(self, value: bool) -> None:
        self._connected = value

    def close(self) -> None:
        self.closed += 1

    async def _call(self, method: str, address: int, count: int, device_id: int) -> Any:
        index = len(self.calls)
        self.calls.append(Call(method, address, count, device_id, self._clock.now))
        if self._on_request is not None:
            self._on_request(index)
        action = self._actions.pop(0)
        self.ends.append(self._clock.now)
        match action.kind:
            case "bits":
                padded = list(action.payload) + [False] * (-len(action.payload) % 8)
                return SimpleNamespace(isError=lambda: False, bits=padded)
            case "registers":
                return SimpleNamespace(isError=lambda: False, registers=action.payload)
            case "error":
                return SimpleNamespace(isError=lambda: True, exception_code=action.payload)
            case "no_reply":
                raise ModbusIOException("no reply")
            case "lost":
                self._connected = False
                raise ConnectionException("lost")
        raise AssertionError(action.kind)

    async def read_coils(self, address: int, *, count: int, device_id: int) -> Any:
        return await self._call("read_coils", address, count, device_id)

    async def read_discrete_inputs(self, address: int, *, count: int, device_id: int) -> Any:
        return await self._call("read_discrete_inputs", address, count, device_id)

    async def read_holding_registers(self, address: int, *, count: int, device_id: int) -> Any:
        return await self._call("read_holding_registers", address, count, device_id)

    async def read_input_registers(self, address: int, *, count: int, device_id: int) -> Any:
        return await self._call("read_input_registers", address, count, device_id)


class FakeLink:
    """A `BlockReader` returning scripted results and recording the specs asked for."""

    def __init__(self, results: list[BlockResult] | Callable[[BlockSpec], BlockResult]) -> None:
        self._results = results
        self.asked: list[BlockSpec] = []

    async def read_block(self, spec: BlockSpec) -> BlockResult:
        self.asked.append(spec)
        if callable(self._results):
            return self._results(spec)
        return self._results.pop(0)

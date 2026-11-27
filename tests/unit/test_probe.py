"""Block plan, run_probe and the CLI (spec 001, tasks 5, 8, 9)."""

import io
import json
from datetime import UTC, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.modbus import readonly_link
from app.modbus.probe import (
    ProbeRun,
    RunEnd,
    extended_plan,
    main,
    run_probe,
    standard_plan,
)
from app.modbus.probe import extended_plan as _ext_plan
from app.modbus.readonly_link import BlockResult, FailReason, Outcome
from app.modbus.registers import Table
from tests.unit.fakes import FakeClient, FakeClock, FakeLink, bits, error, lost, no_reply, registers


def ok(spec):
    return BlockResult(spec, Outcome.OK, values=(0,) * spec.count)


def failed(spec, reason=FailReason.NO_REPLY):
    return BlockResult(spec, Outcome.FAILED, reason=reason)


def refused(spec):
    return BlockResult(spec, Outcome.REFUSED, exception_code=2)


def scripted(*kinds):
    """A FakeLink whose n-th answer follows kinds[n] (default ok)."""
    state = {"n": 0}

    def answer(spec):
        kind = kinds[state["n"]] if state["n"] < len(kinds) else "ok"
        state["n"] += 1
        return {
            "ok": ok,
            "failed": failed,
            "refused": refused,
            "lost": lambda s: failed(s, FailReason.CONNECTION_LOST),
        }[kind](spec)

    return FakeLink(answer)


def test_standard_plan_order_and_contents():
    assert [(s.table, s.start) for s in standard_plan()] == (
        [(Table.COIL, 0), (Table.DISCRETE_INPUT, 0), (Table.DISCRETE_INPUT, 48)]
        + [(Table.HOLDING, a) for a in (0, 3, 6, 9, 12, 15, 18)]
        + [(Table.INPUT, a) for a in (0, 3, 6, 9, 12)]
    )
    assert not any(s.extended for s in standard_plan())


def test_extended_plan_order_and_contents():
    assert [(s.table, s.start) for s in extended_plan()] == [(Table.HOLDING, 24)] + [
        (Table.INPUT, a) for a in (15, 18, 21, 24, 27, 30)
    ]
    assert all(s.extended for s in extended_plan())


async def test_without_extended_flag_no_extended_block():
    link = scripted()
    run = await run_probe(link, extended=False)
    assert tuple(link.asked) == standard_plan()
    assert [r.spec for r in run.results] == list(standard_plan())
    assert run.end is RunEnd.COMPLETE and not run.extended


async def test_with_extended_flag_reads_extended_after_standard():
    link = scripted()
    run = await run_probe(link, extended=True)
    assert tuple(link.asked) == standard_plan() + extended_plan()
    assert run.end is RunEnd.COMPLETE and run.extended


async def test_one_failure_then_ok_continues():
    run = await run_probe(scripted("failed"), extended=False)
    assert run.end is RunEnd.COMPLETE
    assert run.results[0].outcome is Outcome.FAILED
    assert run.results[1].outcome is Outcome.OK


async def test_two_failures_in_a_row_abort_and_skip_extended():
    link = scripted("ok", "failed", "failed")
    run = await run_probe(link, extended=True)
    assert run.end is RunEnd.ABORTED_FAILURES
    assert len(link.asked) == 3
    assert all(r.outcome is Outcome.NOT_ATTEMPTED for r in run.results[3:])
    assert len(run.results) == len(standard_plan()) + len(extended_plan())


async def test_refused_resets_failure_count():
    run = await run_probe(scripted("failed", "refused", "failed"), extended=False)
    assert run.end is RunEnd.COMPLETE


async def test_connection_lost_aborts_on_connection():
    link = scripted("ok", "lost")
    run = await run_probe(link, extended=False)
    assert run.end is RunEnd.ABORTED_CONNECTION
    assert len(link.asked) == 2
    assert run.results[2].outcome is Outcome.NOT_ATTEMPTED


async def test_connection_lost_as_second_failure_is_still_connection_abort():
    run = await run_probe(scripted("failed", "lost"), extended=False)
    assert run.end is RunEnd.ABORTED_CONNECTION


async def test_failure_count_restarts_at_first_extended_block():
    n = len(standard_plan())
    run = await run_probe(scripted(*(["ok"] * (n - 1) + ["failed", "failed"])), extended=True)
    # last standard block failed, first extended block failed: the count restarts, so no abort
    assert run.results[n - 1].outcome is Outcome.FAILED
    assert run.results[n].outcome is Outcome.FAILED
    assert run.results[n + 1].outcome is Outcome.OK
    assert run.end is RunEnd.COMPLETE


async def test_should_stop_interrupts_before_block():
    link = scripted()
    calls = {"n": 0}

    def stop():
        calls["n"] += 1
        return calls["n"] > 4

    run = await run_probe(link, extended=False, should_stop=stop)
    assert run.end is RunEnd.INTERRUPTED
    assert len(link.asked) == 4
    assert all(r.outcome is Outcome.NOT_ATTEMPTED for r in run.results[4:])
    assert len(run.results) == len(standard_plan())


async def test_started_utc_comes_from_now():
    moment = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    run = await run_probe(scripted(), extended=False, now=lambda: moment)
    assert run.started_utc == moment
    assert isinstance(run, ProbeRun)


@given(st.lists(st.sampled_from(["ok", "failed", "refused", "lost"]), max_size=30), st.booleans())
async def test_property_one_result_per_planned_block(kinds, extended):
    link = scripted(*kinds)
    run = await run_probe(link, extended=extended)
    plan = standard_plan() + (extended_plan() if extended else ())
    assert [r.spec for r in run.results] == list(plan)
    assert set(link.asked) <= set(plan)


# ---------------------------------------------------------------------------
# CLI (tasks 8 and 9)
# ---------------------------------------------------------------------------


class Stdin(io.StringIO):
    def __init__(self, text="", tty=True):
        super().__init__(text)
        self._tty = tty

    def isatty(self):
        return self._tty


@pytest.fixture(autouse=True)
def no_real_delays(monkeypatch):
    monkeypatch.setattr(readonly_link, "MIN_GAP_S", 0.0)
    monkeypatch.setattr(readonly_link, "QUIET_AFTER_FAILURE_S", 0.0)


def good(spec):
    return bits([0] * 48) if spec.count == 48 else registers([0] * 3)


def actions_for(extended=False, **replace):
    """One ok action per block; replace={index: Action}."""
    plan = standard_plan() + (_ext_plan() if extended else ())
    out = [good(s) for s in plan]
    for i, a in replace.items():
        out[int(i.removeprefix("i"))] = a
    return out


class Harness:
    def __init__(self, actions, on_request=None):
        self.clock = FakeClock()
        self.client = FakeClient(self.clock, actions, on_request=on_request)
        self.opened: list[tuple[str, int, float]] = []
        self.interrupt = None
        self.out, self.err = io.StringIO(), io.StringIO()
        self.on_open = None
        self.connected_before_first_request = None

    async def open(self, host, port, timeout):
        self.opened.append((host, port, timeout))
        if self.on_open:
            self.on_open()
        return self.client

    def run(self, argv, stdin=None):
        def install(callback):
            self.interrupt = callback

        return main(
            argv,
            stdin=stdin if stdin is not None else Stdin(tty=False),
            stdout=self.out,
            stderr=self.err,
            open=self.open,
            install_interrupt=install,
        )


def harness(extended=False, **replace):
    return Harness(actions_for(extended, **replace))


# ---- task 8: arguments, pre-checks, prompt ----


def test_help_mentions_preconditions_and_exit_statuses_and_opens_nothing(capsys):
    h = harness()
    with pytest.raises(SystemExit) as exc:
        h.run(["--help"])
    assert exc.value.code == 0
    text = capsys.readouterr().out
    assert "WiFi module is unplugged" in text and "controller container is stopped" in text
    for status in ("0 ", "1 ", "2 ", "130"):
        assert status in text
    assert h.opened == []


def test_missing_host_exits_2(capsys):
    with pytest.raises(SystemExit) as exc:
        harness().run([])
    assert exc.value.code == 2


def test_defaults():
    h = harness()
    assert h.run(["gw.local", "--yes"]) == 0
    assert h.opened == [("gw.local", 4196, 3.0)]
    assert {c.device_id for c in h.client.calls} == {1}


@pytest.mark.parametrize(
    ("argv", "name"),
    [
        (["--port", "0"], "--port"),
        (["--port", "65536"], "--port"),
        (["--unit-id", "0"], "--unit-id"),
        (["--unit-id", "248"], "--unit-id"),
        (["--timeout", "0.4"], "--timeout"),
        (["--timeout", "31"], "--timeout"),
    ],
)
def test_invalid_ranges_return_2_and_open_nothing(argv, name):
    h = harness()
    assert h.run(["gw", "--yes", *argv]) == 2
    assert name in h.err.getvalue()
    assert h.opened == [] and h.interrupt is None


def test_boundary_values_are_accepted():
    for argv in (["--port", "1"], ["--port", "65535"], ["--unit-id", "247"], ["--timeout", "0.5"], ["--timeout", "30"]):
        assert harness().run(["gw", "--yes", *argv]) == 0


def test_existing_output_path_returns_2_before_prompt(tmp_path):
    path = tmp_path / "t.json"
    path.write_text("x")
    h = harness()
    stdin = Stdin("yes\n")
    assert h.run(["gw", "--output", str(path)], stdin=stdin) == 2
    assert "--overwrite" in h.err.getvalue()
    assert h.opened == [] and h.out.getvalue() == ""
    assert path.read_text() == "x"


def test_missing_output_directory_returns_2(tmp_path):
    h = harness()
    assert h.run(["gw", "--yes", "--output", str(tmp_path / "nope" / "t.json")]) == 2
    assert "does not exist" in h.err.getvalue() and h.opened == []


def test_unwritable_output_directory_returns_2(tmp_path, monkeypatch):
    monkeypatch.setattr("os.access", lambda *a, **k: False)
    h = harness()
    assert h.run(["gw", "--yes", "--output", str(tmp_path / "t.json")]) == 2
    assert "not writable" in h.err.getvalue() and h.opened == []


def test_overwrite_allows_existing_path(tmp_path):
    path = tmp_path / "t.json"
    path.write_text("old")
    assert harness().run(["gw", "--yes", "--output", str(path), "--overwrite"]) == 0
    assert json.loads(path.read_text())["format_version"] == 1


def test_non_interactive_stdin_without_yes_returns_2_naming_flag():
    h = harness()
    assert h.run(["gw"], stdin=Stdin("yes\n", tty=False)) == 2
    assert "--yes" in h.err.getvalue() and h.opened == []


def test_prompt_accepts_exactly_yes():
    h = harness()
    assert h.run(["gw"], stdin=Stdin("yes\n")) == 0
    assert "WiFi module is unplugged" in h.out.getvalue()
    assert h.opened


@pytest.mark.parametrize("answer", [" yes \n", "\n", "no\n", "YES\n", "yes please\n", ""])
def test_prompt_rejects_everything_else(answer):
    h = harness()
    assert h.run(["gw"], stdin=Stdin(answer)) == 2
    assert h.opened == []


def test_interrupt_at_prompt_returns_130_without_connection():
    h = harness()

    class Interrupting(Stdin):
        def readline(self, *a):
            h.interrupt()

    assert h.run(["gw"], stdin=Interrupting()) == 130
    assert h.opened == []


def test_yes_skips_prompt():
    h = harness()
    assert h.run(["gw", "--yes"], stdin=Stdin("", tty=True)) == 0
    assert "Type" not in h.out.getvalue()


# ---- task 9: run, transcript, exit status ----


def test_connection_failure_returns_2_naming_host_and_port():
    h = harness()

    async def refuse(host, port, timeout):
        raise ConnectionError("x")

    h.open = refuse
    assert h.run(["gw.local", "--yes", "--port", "5000"]) == 2
    assert "gw.local:5000" in h.err.getvalue()


def test_interrupt_during_connection_attempt_returns_130():
    h = harness()
    h.on_open = lambda: h.interrupt()
    # the handler raises KeyboardInterrupt while "waiting"
    assert h.run(["gw", "--yes"]) == 130
    assert h.client.calls == []


def test_clean_run_returns_0_prints_report_and_closes():
    h = harness()
    assert h.run(["gw", "--yes"]) == 0
    assert "== Result ==" in h.out.getvalue() and "run ended: complete" in h.out.getvalue()
    assert h.client.closed == 1
    assert len(h.opened) == 1
    assert len(h.client.calls) == len(standard_plan())


def test_on_connected_called_once_after_open_and_before_first_request():
    seen = []
    h = harness()

    def first_request(index):
        seen.append(("request", index))

    h.client._on_request = first_request
    original_open = h.open

    async def open_and_note(*a):
        seen.append("open")
        return await original_open(*a)

    h.open = open_and_note

    import app.modbus.probe as probe_module

    real_run = probe_module._run

    async def spy(args, open, should_stop, on_connected):
        def wrapped():
            seen.append("connected")
            on_connected()

        return await real_run(args, open, should_stop, wrapped)

    probe_module._run = spy
    try:
        assert h.run(["gw", "--yes"]) == 0
    finally:
        probe_module._run = real_run
    assert seen[:3] == ["open", "connected", ("request", 0)]
    assert seen.count("connected") == 1


def test_failed_standard_block_returns_1():
    assert harness(i3=no_reply()).run(["gw", "--yes"]) == 1


def test_refused_standard_block_returns_1():
    assert harness(i3=error(2)).run(["gw", "--yes"]) == 1


def test_failed_extended_block_alone_returns_0():
    n = len(standard_plan())
    h = harness(extended=True, **{f"i{n}": no_reply()})
    assert h.run(["gw", "--yes", "--extended"]) == 0
    assert "extended: 6 ok, 0 refused, 1 failed, 0 not attempted" in h.out.getvalue()


def test_aborted_extended_run_still_exits_by_standard_blocks():
    n = len(standard_plan())
    h = harness(extended=True, **{f"i{n}": no_reply(), f"i{n + 1}": no_reply()})
    assert h.run(["gw", "--yes", "--extended"]) == 0


def test_connection_loss_returns_1_and_closes():
    h = harness(i2=lost())
    assert h.run(["gw", "--yes"]) == 1
    assert "run ended: aborted on connection loss" in h.out.getvalue()
    assert h.client.closed == 1


def test_transcript_written_exclusive_and_without_host(tmp_path):
    path = tmp_path / "t.json"
    h = harness()
    assert h.run(["secret-gateway.example", "--yes", "--output", str(path), "--port", "5001", "--unit-id", "4"]) == 0
    text = path.read_text()
    assert "secret-gateway" not in text
    data = json.loads(text)
    assert (data["port"], data["unit_id"], data["run_end"]) == (5001, 4, "complete")
    assert len(data["blocks"]) == len(standard_plan())


def test_unwritable_transcript_still_prints_report_and_returns_1(tmp_path, monkeypatch):
    path = tmp_path / "t.json"

    def deny(self, mode="r", *a, **k):
        raise PermissionError("denied")

    monkeypatch.setattr("pathlib.Path.open", deny)
    h = harness()
    assert h.run(["gw", "--yes", "--output", str(path)]) == 1
    assert "== Result ==" in h.out.getvalue()
    assert "denied" in h.err.getvalue()


def test_interrupt_mid_run_returns_130_reports_and_writes_transcript(tmp_path):
    path = tmp_path / "t.json"
    h = harness()
    h.client._on_request = lambda index: h.interrupt() if index == 2 else None
    assert h.run(["gw", "--yes", "--output", str(path)]) == 130
    assert "run ended: interrupted" in h.out.getvalue()
    assert len(h.client.calls) == 3
    data = json.loads(path.read_text())
    assert data["run_end"] == "interrupted"
    assert data["blocks"][2]["outcome"] == "ok" and data["blocks"][3]["outcome"] == "not_attempted"
    assert h.client.closed == 1


def test_interrupt_during_last_block_returns_130_and_reports_interrupted():
    h = harness()
    last = len(standard_plan()) - 1
    h.client._on_request = lambda index: h.interrupt() if index == last else None
    assert h.run(["gw", "--yes"]) == 130
    assert "run ended: interrupted" in h.out.getvalue()


def test_options_never_change_which_methods_are_called(tmp_path):
    allowed = set(readonly_link.READ_METHODS.values())
    for extra in ([], ["--extended"], ["--output", str(tmp_path / "a.json")], ["--extended", "--overwrite"]):
        h = harness(extended="--extended" in extra)
        h.run(["gw", "--yes", *extra])
        assert {c.method for c in h.client.calls} <= allowed


def test_output_path_that_is_a_directory_returns_2_even_with_overwrite(tmp_path):
    h = harness()
    assert h.run(["gw", "--yes", "--output", str(tmp_path), "--overwrite"]) == 2
    assert "directory" in h.err.getvalue() and h.opened == []


def test_client_closed_when_interrupt_lands_right_after_open():
    h = harness()
    import app.modbus.probe as probe_module

    real_run = probe_module._run

    async def spy(args, open, should_stop, on_connected):
        def boom():
            raise KeyboardInterrupt

        return await real_run(args, open, should_stop, boom)

    probe_module._run = spy
    try:
        assert h.run(["gw", "--yes"]) == 130
    finally:
        probe_module._run = real_run
    assert h.client.closed == 1
    assert h.client.calls == []


def test_run_passes_the_stop_predicate_to_the_link(monkeypatch):
    import app.modbus.probe as probe_module

    seen = {}
    real = probe_module.ReadOnlyLink

    def spy(client, **kwargs):
        seen.update(kwargs)
        return real(client, **kwargs)

    monkeypatch.setattr(probe_module, "ReadOnlyLink", spy)
    h = harness()
    assert h.run(["gw", "--yes"]) == 0
    assert callable(seen["should_stop"])
    h.interrupt()  # phase is "running" no longer matters: the flag is what the predicate reads
    assert seen["should_stop"]() is True


def test_interrupt_while_report_is_printed_is_reflected_in_transcript_and_exit(tmp_path):
    path = tmp_path / "t.json"
    h = harness()

    class Out(io.StringIO):
        def write(self, text):
            if "== Result ==" in text:
                h.interrupt()
            return super().write(text)

    h.out = Out()
    assert h.run(["gw", "--yes", "--output", str(path)]) == 130
    assert json.loads(path.read_text())["run_end"] == "interrupted"


def test_interrupt_while_transcript_is_built_rewrites_it_as_interrupted(tmp_path, monkeypatch):
    import app.modbus.probe as probe_module

    path = tmp_path / "t.json"
    h = harness()
    real_dumps = json.dumps
    calls = {"n": 0}

    def dumps(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            h.interrupt()
        return real_dumps(*a, **k)

    monkeypatch.setattr(probe_module.json, "dumps", dumps)
    assert h.run(["gw", "--yes", "--output", str(path)]) == 130
    assert real_dumps(json.loads(path.read_text())["run_end"]) == '"interrupted"'

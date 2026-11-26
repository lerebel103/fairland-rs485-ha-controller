"""Report and transcript (spec 001, tasks 6 and 7). ProbeRun values are built by hand."""

import json
import re
from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.modbus.probe import ProbeRun, RunEnd, extended_plan, standard_plan
from app.modbus.probe_report import TRANSCRIPT_FORMAT_VERSION, build_transcript, render_report
from app.modbus.readonly_link import BlockResult, BlockSpec, FailReason, Outcome
from app.modbus.registers import Table

STARTED = datetime(2026, 11, 26, 3, 15, 0, tzinfo=UTC)

# Raw values by (table, address) for the "pump" in these tests.
HOLDING = {0: 1, 1: 1, 2: 112, 3: 112, 4: 100}
INPUT = {0: 50, 2: 238, 3: 108, 4: 112, 5: 96, 11: 53}


def _values(spec, overrides=None):
    data = {Table.HOLDING: dict(HOLDING), Table.INPUT: dict(INPUT)}.get(spec.table, {})
    if overrides and spec.table in overrides:
        data.update(overrides[spec.table])
    if spec.table is Table.COIL:
        return tuple(1 if i == 0 else 0 for i in range(48))
    if spec.table is Table.DISCRETE_INPUT:
        return tuple(1 if (spec.start == 0 and i == 0) else 0 for i in range(48))
    return tuple(data.get(spec.start + i, 0) for i in range(3))


def make_run(*, extended=False, end=RunEnd.COMPLETE, override=None, overrides=None):
    """override: {(table, start): BlockResult}"""
    override = override or {}
    plan = standard_plan() + (extended_plan() if extended else ())
    results = tuple(
        override.get((s.table, s.start)) or BlockResult(s, Outcome.OK, values=_values(s, overrides)) for s in plan
    )
    return ProbeRun(results, extended, end, STARTED)


def failed(table, start, reason=FailReason.NO_REPLY, code=None, extended=False):
    return BlockResult(BlockSpec(table, start, extended), Outcome.FAILED, reason=reason, exception_code=code)


def refused(table, start, code=2, extended=False):
    return BlockResult(BlockSpec(table, start, extended), Outcome.REFUSED, exception_code=code)


def not_attempted(table, start, extended=False):
    return BlockResult(BlockSpec(table, start, extended), Outcome.NOT_ATTEMPTED)


def lines(text):
    return [re.sub(r" +", " ", line).strip() for line in text.splitlines()]


def section(text, heading_prefix):
    out, on = [], False
    for line in lines(text):
        if line.startswith("== "):
            on = line.startswith(heading_prefix)
            continue
        if on and line:
            out.append(line)
    return out


def test_section_order_and_headings():
    text = render_report(make_run(extended=True))
    headings = [x for x in lines(text) if x.startswith("== ")]
    assert headings == [
        "== Summary: compare with the pump display ==",
        "== Active faults ==",
        "== Standard blocks ==",
        "== Extended blocks (outside the vendor's allowed first addresses; unverified) ==",
        "== Result ==",
    ]


def test_register_line_content():
    std = section(render_report(make_run()), "== Standard")
    assert "0 operating_mode Function selection raw 1 heating (0 auto, 1 heating, 2 cooling.)" in std
    assert "2 target_temp_auto Auto mode target temperature raw 112 26.0 °C" in std


@pytest.mark.parametrize(
    ("block", "expected"),
    [
        (refused(Table.HOLDING, 15), "[refused: exception 0x02] holding 15-17"),
        (failed(Table.INPUT, 9), "[failed: no reply] input 9-11"),
        (failed(Table.INPUT, 9, FailReason.WRONG_LENGTH), "[failed: wrong length] input 9-11"),
        (failed(Table.INPUT, 9, FailReason.CONNECTION_LOST), "[failed: connection lost] input 9-11"),
        (
            failed(Table.INPUT, 9, FailReason.GATEWAY_EXCEPTION, 0x0B),
            "[failed: gateway exception (exception 0x0B)] input 9-11",
        ),
        (not_attempted(Table.INPUT, 9), "[not attempted] input 9-11"),
    ],
)
def test_block_line_forms(block, expected):
    run = make_run(override={(block.spec.table, block.spec.start): block})
    assert expected in lines(render_report(run))
    assert "[ok] holding 0-2" in lines(render_report(run))


def test_gateway_exception_code_without_value_still_renders():
    block = failed(Table.INPUT, 9, FailReason.GATEWAY_EXCEPTION, None)
    assert "[failed: gateway exception] input 9-11" in lines(
        render_report(make_run(override={(Table.INPUT, 9): block}))
    )


def test_value_formats():
    text = render_report(make_run())
    std = section(text, "== Standard")
    assert "0 power Power switch raw 1 on" in std
    assert any(s.startswith("3 inlet_temp") and s.endswith("raw 108 24.0 °C") for s in std)
    assert any(s.startswith("11 compressor_current") and "raw 53 5.3 A" in s for s in std)
    assert any(s.startswith("2 pfc_voltage") and "raw 238 238 V" in s for s in std)


def test_unmapped_address_shows_raw_only():
    run = make_run(overrides={Table.HOLDING: {13: 7}})
    assert "13 - raw 7" in section(render_report(run), "== Standard")


def test_ok_bit_block_shows_all_48_raw_bits_in_address_order_including_block_48():
    bits48 = tuple(1 if i in (3, 47) else 0 for i in range(48))
    run = make_run(
        override={
            (Table.DISCRETE_INPUT, 48): BlockResult(BlockSpec(Table.DISCRETE_INPUT, 48), Outcome.OK, values=bits48)
        }
    )
    std = section(render_report(run), "== Standard")
    expected = "raw bits: " + " ".join("".join(str(b) for b in bits48[i : i + 8]) for i in range(0, 48, 8))
    assert expected in std
    assert "see Active faults" in std
    first = next(s for s in std if s.startswith("raw bits: 1000000"))
    assert len(first.removeprefix("raw bits: ").replace(" ", "")) == 48


def test_coil_block_other_bits_line():
    bits = tuple(1 if i in (0, 5, 9) else 0 for i in range(48))
    run = make_run(override={(Table.COIL, 0): BlockResult(BlockSpec(Table.COIL, 0), Outcome.OK, values=bits)})
    std = section(render_report(run), "== Standard")
    assert "other bits set: 5, 9" in std
    assert "other bits set: none" in std  # DI block 0 has only mapped bits set


@pytest.mark.parametrize(
    ("raw", "name"),
    [(0, "auto"), (1, "heating"), (2, "cooling"), (9, "unknown")],
)
def test_operating_mode_names(raw, name):
    run = make_run(overrides={Table.HOLDING: {0: raw}})
    assert any(x.startswith(f"operating_mode raw {raw} {name}") for x in section(render_report(run), "== Summary"))


@pytest.mark.parametrize(("raw", "name"), [(0, "smart"), (2, "super silence"), (3, "turbo"), (7, "unknown")])
def test_power_mode_names(raw, name):
    run = make_run(overrides={Table.HOLDING: {1: raw}})
    assert any(x.startswith(f"power_mode raw {raw} {name}") for x in section(render_report(run), "== Summary"))


def test_faults_listed_none_and_unavailable():
    bits = tuple(1 if i == 3 else 0 for i in range(48))
    listed = make_run(
        override={(Table.DISCRETE_INPUT, 48): BlockResult(BlockSpec(Table.DISCRETE_INPUT, 48), Outcome.OK, values=bits)}
    )
    assert section(render_report(listed), "== Active faults") == ["E3 protection No water flow"]
    assert section(render_report(make_run()), "== Active faults") == ["none"]
    bad = make_run(override={(Table.DISCRETE_INPUT, 48): failed(Table.DISCRETE_INPUT, 48)})
    assert section(render_report(bad), "== Active faults") == ["unavailable"]


@pytest.mark.parametrize(
    ("overrides", "key", "why"),
    [
        ({Table.HOLDING: {2: 200}}, "target_temp_auto", "outside raw range"),
        ({Table.HOLDING: {2: 101}}, "target_temp_auto", "off raw step"),
        ({Table.HOLDING: {0: 5}}, "operating_mode", "outside raw range"),
    ],
)
def test_suspect_reasons(overrides, key, why):
    std = section(render_report(make_run(overrides=overrides)), "== Standard")
    line = next(s for s in std if f" {key} " in s)
    assert f"SUSPECT ({why})" in line


def test_suspect_implausible_temperature():
    # exhaust_temp is temp type 2 (raw / 2): raw 300 is 150 degC
    std = section(render_report(make_run(overrides={Table.INPUT: {6: 300}})), "== Standard")
    line = next(x for x in std if " exhaust_temp " in x)
    assert "SUSPECT (implausible temperature)" in line


def test_suspect_zero_on_input_15_to_20_takes_precedence():
    run = make_run(extended=True, overrides={Table.INPUT: {15: 0}})
    line = next(x for x in section(render_report(run), "== Extended") if " auto_temp_min " in x)
    assert "SUSPECT (0 means unsupported)" in line


def test_summary_active_setpoint_per_mode():
    for mode, key in [(0, "target_temp_auto"), (1, "target_temp_heating"), (2, "target_temp_cooling")]:
        summary = section(render_report(make_run(overrides={Table.HOLDING: {0: mode}})), "== Summary")
        keys = [s.split()[0] for s in summary]
        assert key in keys
        assert len([k for k in keys if k.startswith("target_temp_")]) == 1


def test_summary_shows_all_setpoints_when_mode_unknown_or_unavailable():
    for run in (
        make_run(overrides={Table.HOLDING: {0: 7}}),
        make_run(override={(Table.HOLDING, 0): refused(Table.HOLDING, 0)}),
    ):
        keys = [s.split()[0] for s in section(render_report(run), "== Summary")]
        assert {"target_temp_auto", "target_temp_heating", "target_temp_cooling"} <= set(keys)


def test_estimated_power_present():
    summary = section(render_report(make_run()), "== Summary")
    assert "estimated compressor power 1261 W (estimated: current x PFC voltage)" in summary  # 5.3 A x 238 V


def test_unavailable_never_a_zero():
    bad = make_run(
        override={
            (Table.HOLDING, 0): refused(Table.HOLDING, 0),
            (Table.INPUT, 3): failed(Table.INPUT, 3),
            (Table.INPUT, 9): not_attempted(Table.INPUT, 9),
            (Table.COIL, 0): failed(Table.COIL, 0),
            (Table.DISCRETE_INPUT, 0): failed(Table.DISCRETE_INPUT, 0),
        }
    )
    summary = section(render_report(bad), "== Summary")
    for label in (
        "power (coil 0)",
        "running (discrete input 0)",
        "operating_mode",
        "power_mode",
        "inlet_temp",
        "estimated compressor power",
    ):
        assert f"{label} unavailable" in summary
    std = "\n".join(section(render_report(bad), "== Standard"))
    assert "inlet_temp" not in std
    assert "operating_mode" not in std


def test_estimate_unavailable_when_an_input_block_failed():
    bad = make_run(override={(Table.INPUT, 9): failed(Table.INPUT, 9)})
    # compressor_current is input 11, in block 9
    assert "estimated compressor power unavailable" in section(render_report(bad), "== Summary")


def test_counts_and_run_ended():
    run = make_run(
        end=RunEnd.ABORTED_FAILURES,
        override={
            (Table.HOLDING, 15): refused(Table.HOLDING, 15),
            (Table.INPUT, 9): failed(Table.INPUT, 9),
            (Table.INPUT, 12): not_attempted(Table.INPUT, 12),
        },
    )
    result = section(render_report(run), "== Result")
    n = len(standard_plan())
    assert f"standard: {n - 3} ok, 1 refused, 1 failed, 1 not attempted" in result
    assert "run ended: aborted after consecutive failures" in result
    assert not any(s.startswith("extended:") for s in result)


@pytest.mark.parametrize(
    ("end", "text"),
    [
        (RunEnd.COMPLETE, "complete"),
        (RunEnd.ABORTED_CONNECTION, "aborted on connection loss"),
        (RunEnd.INTERRUPTED, "interrupted"),
    ],
)
def test_run_ended_text(end, text):
    assert f"run ended: {text}" in section(render_report(make_run(end=end)), "== Result")


def test_no_extended_section_without_flag():
    text = render_report(make_run())
    assert "Extended" not in text
    assert "board version" not in text


def test_extended_section_labelled_and_counted():
    text = render_report(make_run(extended=True))
    assert "== Extended blocks (outside the vendor's allowed first addresses; unverified) ==" in text
    assert "extended: 7 ok, 0 refused, 0 failed, 0 not attempted" in section(text, "== Result")
    ext = section(text, "== Extended")
    assert "[ok] holding 24-26" in ext
    assert "[ok] input 30-32" in ext


def test_ascii_lines_in_both_renderings():
    ver = {21: ord("V"), 22: ord("1"), 23: ord("."), 24: ord("0"), 25: ord("2")}
    model = {26: ord("A"), 27: ord("C"), 28: 0x4132, 29: 0x0031}
    run = make_run(extended=True, overrides={Table.INPUT: {**ver, **model}})
    ext = section(render_report(run), "== Extended")
    assert 'board version (unverified) low byte: "V1.02" two bytes: ".V.1...0.2"' in ext
    assert 'model code (unverified) low byte: "AC21" two bytes: ".A.CA2.1"' in ext


def test_ascii_placeholders_for_unavailable_and_unprintable():
    run = make_run(
        extended=True,
        override={(Table.INPUT, 21): failed(Table.INPUT, 21, extended=True)},
        overrides={Table.INPUT: {24: 0x07, 25: 0x20}},
    )
    board = next(x for x in section(render_report(run), "== Extended") if x.startswith("board version"))
    assert board == 'board version (unverified) low byte: "???. " two bytes: "??????... "'


def test_input_30_and_31_labels():
    ext = section(render_report(make_run(extended=True, overrides={Table.INPUT: {30: 238, 31: 5}})), "== Extended")
    assert "supply voltage (unverified) raw 238" in ext
    assert "compressor restart delay s (unverified) raw 5" in ext
    bad = make_run(extended=True, override={(Table.INPUT, 30): failed(Table.INPUT, 30, extended=True)})
    ext = section(render_report(bad), "== Extended")
    assert "supply voltage (unverified) unavailable" in ext
    assert "compressor restart delay s (unverified) unavailable" in ext


# ---- transcript ----


def transcript(run, **kw):
    return build_transcript(run, port=4196, unit_id=1, timeout_s=3.0, probe_version="0.0.1", **kw)


def test_transcript_keys_are_exactly_the_schema():
    t = transcript(make_run())
    assert set(t) == {
        "format_version",
        "probe_version",
        "started_utc",
        "port",
        "unit_id",
        "timeout_s",
        "extended",
        "run_end",
        "blocks",
    }
    assert t["format_version"] == TRANSCRIPT_FORMAT_VERSION == 1
    assert set(t["blocks"][0]) == {
        "table",
        "start",
        "count",
        "extended",
        "outcome",
        "reason",
        "exception_code",
        "values",
    }


def test_transcript_started_utc_is_utc_with_z():
    local = datetime(2026, 11, 26, 13, 15, 0, tzinfo=timezone(timedelta(hours=10)))
    run = ProbeRun((), False, RunEnd.COMPLETE, local)
    assert transcript(run)["started_utc"] == "2026-11-26T03:15:00Z"


def test_transcript_values_null_unless_ok_and_reasons():
    run = make_run(
        override={
            (Table.HOLDING, 15): refused(Table.HOLDING, 15, 3),
            (Table.INPUT, 9): failed(Table.INPUT, 9, FailReason.GATEWAY_EXCEPTION, 0x0A),
            (Table.INPUT, 12): not_attempted(Table.INPUT, 12),
        }
    )
    blocks = {(b["table"], b["start"]): b for b in transcript(run)["blocks"]}
    ok_block = blocks[("holding", 0)]
    assert ok_block["values"] == [1, 1, 112] and ok_block["reason"] is None and ok_block["exception_code"] is None
    r = blocks[("holding", 15)]
    assert (r["outcome"], r["exception_code"], r["reason"], r["values"]) == ("refused", 3, None, None)
    gw = blocks[("input", 9)]
    assert (gw["outcome"], gw["reason"], gw["exception_code"], gw["values"]) == (
        "failed",
        "gateway_exception",
        10,
        None,
    )
    na = blocks[("input", 12)]
    assert (na["outcome"], na["values"]) == ("not_attempted", None)


@pytest.mark.parametrize("end", [RunEnd.ABORTED_FAILURES, RunEnd.INTERRUPTED])
def test_transcript_aborted_and_interrupted(end):
    run = make_run(end=end, override={(Table.INPUT, 12): not_attempted(Table.INPUT, 12)})
    t = transcript(run)
    assert t["run_end"] == end.value
    assert t["blocks"][-1]["outcome"] == "not_attempted"


def test_transcript_extended_blocks_absent_without_flag():
    assert not any(b["extended"] for b in transcript(make_run())["blocks"])
    assert sum(b["extended"] for b in transcript(make_run(extended=True))["blocks"]) == 7


def test_transcript_has_no_host_and_is_json_serialisable():
    t = transcript(make_run(extended=True))
    text = json.dumps(t)
    assert "host" not in text and "gateway" not in text
    assert json.loads(text) == t

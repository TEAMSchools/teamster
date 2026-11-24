from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date
from pathlib import Path
from types import ModuleType

import pytest

SKILL_SCRIPTS = (
    Path(__file__).resolve().parents[2] / ".claude/skills/service-playbook/scripts"
)


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SKILL_SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


cap = _load("capacity")

YEAR_START = date(2026, 8, 17)
YEAR_END = date(2027, 6, 14)


def test_network_blocked_ignores_one_region_break():
    closures = [
        cap.sd.Closure(
            date(2027, 3, 22), date(2027, 3, 26), "Spring", frozenset({"Miami"})
        ),
        cap.sd.Closure(
            date(2026, 12, 21),
            date(2026, 12, 25),
            "Winter",
            frozenset(cap.sd.REGIONS),
        ),
    ]
    blocked = cap.network_blocked(closures, [2026])
    assert date(2027, 3, 22) not in blocked
    assert date(2026, 12, 21) in blocked
    assert date(2026, 11, 23) in blocked  # Thanksgiving week


def test_window_normalizes_to_monday():
    w = cap.Window("r2", date(2026, 12, 2), date(2026, 12, 11))
    assert (w.open_week, w.close_week) == (date(2026, 11, 30), date(2026, 12, 7))


def test_negative_offset_skips_thanksgiving():
    w = cap.Window("r2", date(2026, 11, 30), date(2026, 12, 7))
    s = cap.Step("Dashboard refresh", "open", -1, 1, 2.0, "owner")
    assert cap.step_weeks(s, w, frozenset({date(2026, 11, 23)})) == [date(2026, 11, 16)]


def test_offset_zero_stays_in_blocked_anchor_week():
    w = cap.Window("r3", date(2026, 12, 21), date(2027, 1, 11))
    s = cap.Step("Reminders on", "open", 0, 1, 1.0, "owner")
    assert cap.step_weeks(s, w, frozenset({date(2026, 12, 21)})) == [date(2026, 12, 21)]


def test_duration_skips_blocked_weeks():
    w = cap.Window("r3", date(2026, 12, 14), date(2027, 1, 11))
    s = cap.Step("Monitor", "open", 0, 3, 0.5, "owner")
    blocked = frozenset({date(2026, 12, 21), date(2026, 12, 28)})
    assert cap.step_weeks(s, w, blocked) == [
        date(2026, 12, 14),
        date(2027, 1, 4),
        date(2027, 1, 11),
    ]


def test_monthly_hours_by_monday_month_and_rounds_filter():
    windows = [
        cap.Window("r1", date(2026, 10, 19), date(2026, 11, 2)),
        cap.Window("r2", date(2026, 11, 30), date(2026, 12, 7)),
    ]
    steps = [
        cap.Step("Reminders off", "close", 0, 1, 1.0, "owner"),
        cap.Step("Publish", "close", 1, 1, 3.0, "owner", rounds=("r1",)),
    ]
    hours = cap.monthly_hours(
        steps, windows, [], frozenset(), 2026, YEAR_START, YEAR_END
    )
    assert len(hours) == 12
    assert hours[4] == 4.0  # November: r1 off (Nov 2) + publish (Nov 9)
    assert hours[5] == 1.0  # December: r2 off (Dec 7)
    assert sum(hours) == 5.0


def test_standing_school_year_skips_blocked():
    hours = cap.monthly_hours(
        [],
        [],
        [cap.Standing("Tickets", 1.0, "school_year")],
        frozenset({date(2026, 11, 23)}),
        2026,
        date(2026, 11, 2),
        date(2026, 11, 30),
    )
    assert hours[4] == 4.0  # Nov 2, 9, 16, 30 (23 blocked)
    assert sum(hours) == 4.0


def test_step_outside_school_year_raises():
    w = cap.Window("r1", date(2026, 7, 6), date(2026, 7, 13))
    s = cap.Step("Prep", "open", -2, 1, 1.0, "owner")
    with pytest.raises(ValueError, match="Prep.*r1"):
        cap.monthly_hours([s], [w], [], frozenset(), 2026, YEAR_START, YEAR_END)


def test_offset_between_counts_unblocked_weeks_and_round_trips():
    blocked = frozenset({date(2026, 11, 23)})
    w = cap.Window("r2", date(2026, 11, 16), date(2026, 12, 7))
    # Due Nov 30 from an open week of Nov 16: Thanksgiving week does not count.
    offset = cap.offset_between(w.open_week, date(2026, 11, 30), blocked)
    assert offset == 1
    s = cap.Step("Check refresh", "open", offset, 1, 1.0, "owner")
    assert cap.step_weeks(s, w, blocked) == [date(2026, 11, 30)]


def test_offset_between_due_in_blocked_week_before_anchor_is_zero():
    blocked = frozenset({date(2026, 11, 23)})
    assert cap.offset_between(date(2026, 11, 30), date(2026, 11, 25), blocked) == 0
    assert cap.offset_between(date(2026, 11, 30), date(2026, 11, 18), blocked) == -1


def test_step_after_june_raises():
    w = cap.Window("r4", date(2027, 6, 21), date(2027, 6, 28))
    s = cap.Step("Publish", "close", 1, 1, 1.0, "owner")
    with pytest.raises(ValueError, match="Publish.*r4"):
        cap.monthly_hours([s], [w], [], frozenset(), 2026, YEAR_START, YEAR_END)


def test_standing_all_counts_every_monday_including_blocked():
    hours = cap.monthly_hours(
        [],
        [],
        [cap.Standing("On call", 1.0, "all")],
        frozenset({date(2026, 11, 23)}),
        2026,
        YEAR_START,
        YEAR_END,
    )
    assert hours[0] == 4.0  # July 2026 Mondays: 6, 13, 20, 27
    assert hours[4] == 5.0  # November: 2, 9, 16, 23, 30, blocked week included
    assert sum(hours) == 52.0


def test_standing_weeks_outside_school_year_raise():
    with pytest.raises(ValueError, match="first-week"):
        cap.monthly_hours(
            [],
            [],
            [cap.Standing("Tickets", 1.0, "school_year")],
            frozenset(),
            2026,
            date(2026, 6, 22),
            YEAR_END,
        )


def _write(
    tmp_path, spec, breaks="Month,Date,Day,Holiday/Event,Newark,Camden,Miami,Paterson\n"
):
    sp, bp = tmp_path / "spec.json", tmp_path / "breaks.csv"
    sp.write_text(json.dumps(spec))
    bp.write_text(breaks)
    return [
        "--spec",
        str(sp),
        "--breaks",
        str(bp),
        "--school-year",
        "2026",
        "--first-week",
        "2026-08-17",
        "--last-week",
        "2027-06-14",
    ]


def test_main_empty_rounds_places_step_nowhere(tmp_path, capsys):
    spec = {
        "windows": [
            {"round_key": "r1", "open_week": "2026-10-19", "close_week": "2026-11-02"}
        ],
        "steps": [
            {
                "name": "Never",
                "anchor": "open",
                "offset_weeks": 0,
                "duration_weeks": 1,
                "hours_per_week": 5,
                "role": "owner",
                "rounds": [],
            },
            {
                "name": "Always",
                "anchor": "open",
                "offset_weeks": 0,
                "duration_weeks": 1,
                "hours_per_week": 1,
                "role": "owner",
                "rounds": None,
            },
        ],
    }
    assert cap.main(_write(tmp_path, spec)) == 0
    out = json.loads(capsys.readouterr().out)
    assert [s["step"] for s in out["steps"]] == ["Always"]
    assert out["hours_per_year"] == 1.0


def test_main_bad_spec_exits_2(tmp_path, capsys):
    spec = {
        "steps": [
            {
                "name": "x",
                "anchor": "middle",
                "offset_weeks": 0,
                "duration_weeks": 1,
                "hours_per_week": 1,
                "role": "o",
            }
        ]
    }
    assert cap.main(_write(tmp_path, spec)) == 2
    assert "anchor must be open or close" in capsys.readouterr().err


def test_unknown_round_raises():
    s = cap.Step("Publish", "close", 1, 1, 3.0, "owner", rounds=("r9",))
    with pytest.raises(ValueError, match="r9"):
        cap.monthly_hours([s], [], [], frozenset(), 2026, YEAR_START, YEAR_END)

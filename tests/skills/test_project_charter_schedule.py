from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path
from types import ModuleType

import pytest

SKILL_SCRIPTS = (
    Path(__file__).resolve().parents[2] / ".claude/skills/project-charter/scripts"
)


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SKILL_SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sd = _load("schedule_dates")


def rows(*r):
    """Breaks-tab rows: (Month, Date, Newark, Camden, Miami, Paterson)."""
    return [
        {
            "Month": m,
            "Date": d,
            "Day": "",
            "Holiday/Event": "x",
            "Newark": n,
            "Camden": c,
            "Miami": mi,
            "Paterson": p,
        }
        for m, d, n, c, mi, p in r
    ]


# parse_breaks


def test_single_day_closure():
    [c] = sd.parse_breaks(
        rows(("November", "11", "Yes", "Yes", "No", "Yes")), 2026, ["Newark"]
    )
    assert (c.start, c.end) == (date(2026, 11, 11), date(2026, 11, 11))


def test_range_within_month():
    [c] = sd.parse_breaks(
        rows(("November", "25 - 27", "Yes", "Yes", "Yes", "Yes")), 2026, sd.REGIONS
    )
    assert (c.start, c.end) == (date(2026, 11, 25), date(2026, 11, 27))


def test_range_crossing_year():
    [c] = sd.parse_breaks(
        rows(("December", "Dec 21 - Jan 1", "Yes", "Yes", "Yes", "Yes")),
        2026,
        sd.REGIONS,
    )
    assert (c.start, c.end) == (date(2026, 12, 21), date(2027, 1, 1))


def test_spring_month_takes_next_year():
    [c] = sd.parse_breaks(
        rows(("April", "3", "Yes", "No", "No", "No")), 2026, ["Newark"]
    )
    assert c.start == date(2027, 4, 3)


def test_out_of_scope_region_ignored():
    assert (
        sd.parse_breaks(
            rows(("November", "11", "No", "Yes", "No", "No")), 2026, ["Newark"]
        )
        == []
    )


def test_region_yes_is_case_sensitive():
    assert (
        sd.parse_breaks(
            rows(("November", "11", "yes", "Y", "", "YES")), 2026, sd.REGIONS
        )
        == []
    )


def test_unparseable_date_names_row():
    with pytest.raises(ValueError, match="Holiday/Event=x"):
        sd.parse_breaks(
            rows(("November", "TBD", "Yes", "No", "No", "No")), 2026, ["Newark"]
        )


def test_blank_month_continues_previous_row():
    out = sd.parse_breaks(
        rows(
            ("November", "6", "Yes", "No", "No", "Yes"),
            ("", "25-27", "Yes", "Yes", "No", "Yes"),
        ),
        2026,
        ["Newark"],
    )
    assert out[1].start == date(2026, 11, 25)


def test_end_month_in_parens():
    [c] = sd.parse_breaks(
        rows(("March", "29-2 (Apr)", "Yes", "Yes", "No", "No")), 2026, ["Newark"]
    )
    assert (c.start, c.end) == (date(2027, 3, 29), date(2027, 4, 2))


def test_short_row_missing_region_column():
    row = {
        "Month": "May",
        "Date": "31",
        "Day": "",
        "Holiday/Event": "x",
        "Newark": "Yes",
        "Camden": "Yes",
        "Miami": "Yes",
        "Paterson": None,
    }
    [c] = sd.parse_breaks([row], 2026, sd.REGIONS)
    assert c.start == date(2027, 5, 31)


# blocked_weeks / closed_days


def test_thanksgiving_2026():
    assert sd.thanksgiving(2026) == date(2026, 11, 26)


def test_three_day_closure_blocks_week():
    c = sd.Closure(date(2026, 12, 23), date(2026, 12, 25), "x")  # Wed-Fri
    assert date(2026, 12, 21) in sd.blocked_weeks([c], [2026])


def test_two_day_closure_does_not_block():
    c = sd.Closure(date(2026, 12, 24), date(2026, 12, 25), "x")
    assert sd.blocked_weeks([c], [2026]) == frozenset({date(2026, 11, 23)})


def test_straddling_closure_blocks_neither_week():
    c = sd.Closure(date(2027, 2, 11), date(2027, 2, 15), "x")  # Thu-Mon
    assert sd.blocked_weeks([c], [2026]) == frozenset({date(2026, 11, 23)})


def test_thanksgiving_week_blocked_without_a_row():
    assert sd.blocked_weeks([], [2026, 2027]) == frozenset(
        {date(2026, 11, 23), date(2027, 11, 22)}
    )


def test_closed_days_skip_weekends():
    c = sd.Closure(date(2026, 12, 18), date(2026, 12, 21), "x")  # Fri-Mon
    assert sd.closed_days([c]) == frozenset({date(2026, 12, 18), date(2026, 12, 21)})


# place / CLI

END = date(2027, 6, 18)


@pytest.fixture
def closures():
    # Wed-Fri 2027-02-17..19 for every region: blocks the week of 2/15
    return [sd.Closure(date(2027, 2, 17), date(2027, 2, 19), "mid-winter")]


def test_one_week_row_lands_first_friday(closures):
    [p] = sd.place(
        [sd.PlanRow("a", "m1", "milestone", 1)], date(2027, 1, 11), closures, END
    )
    assert (p.due, p.rule, p.note) == (date(2027, 1, 15), "friday", "")


def test_start_midweek_counts_that_week(closures):
    [p] = sd.place(
        [sd.PlanRow("a", "m1", "milestone", 1)], date(2027, 1, 13), closures, END
    )
    assert p.due == date(2027, 1, 15)


def test_start_on_weekend_counts_next_week(closures):
    [p] = sd.place(
        [sd.PlanRow("a", "m1", "milestone", 1)], date(2027, 1, 16), closures, END
    )
    assert p.due == date(2027, 1, 22)


def test_blocked_week_is_skipped(closures):
    [p] = sd.place(
        [sd.PlanRow("a", "m1", "milestone", 2)], date(2027, 2, 8), closures, END
    )
    assert p.due == date(2027, 2, 26)  # week of 2/15 skipped


def test_closed_friday_moves_to_thursday():
    c = [sd.Closure(date(2027, 1, 15), date(2027, 1, 15), "x")]
    [p] = sd.place([sd.PlanRow("a", "m1", "milestone", 1)], date(2027, 1, 11), c, END)
    assert (p.due, p.rule) == (date(2027, 1, 14), "closed friday -> thursday")


def test_after_starts_monday_after_predecessor(closures):
    out = sd.place(
        [
            sd.PlanRow("a", "m1", "milestone", 1),
            sd.PlanRow("b", "t1", "task", 1, after="m1"),
        ],
        date(2027, 1, 11),
        closures,
        END,
    )
    assert out[1].due == date(2027, 1, 22)


def test_parallel_workstreams_start_together(closures):
    out = sd.place(
        [sd.PlanRow("a", "m1", "milestone", 1), sd.PlanRow("b", "m2", "milestone", 1)],
        date(2027, 1, 11),
        closures,
        END,
    )
    assert out[0].due == out[1].due


def test_override_shifts_follower_past_blocked_week(closures):
    out = sd.place(
        [
            sd.PlanRow("a", "m1", "milestone", 1, override=date(2027, 2, 12)),
            sd.PlanRow("a", "t1", "task", 1, after="m1"),
        ],
        date(2027, 1, 11),
        closures,
        END,
    )
    assert (out[0].note, out[1].due) == ("override", date(2027, 2, 26))


def test_past_calendar_is_unverified(closures):
    [p] = sd.place(
        [sd.PlanRow("a", "m1", "milestone", 1)], date(2027, 6, 21), closures, END
    )
    assert p.note == "unverified: calendar not published"


def test_unknown_after_raises(closures):
    with pytest.raises(ValueError, match="m1"):
        sd.place(
            [
                sd.PlanRow("a", "m1", "milestone", 1),
                sd.PlanRow("a", "t1", "task", 1, after="nope"),
            ],
            date(2027, 1, 11),
            closures,
            END,
        )


def test_cli_prints_table_and_end_warning(tmp_path, capsys):
    breaks = tmp_path / "breaks.csv"
    breaks.write_text(
        "Month,Date,Day,Holiday/Event,Newark,Camden,Miami,Paterson\n"
        "February,17 - 19,Wed,Mid-winter,Yes,Yes,Yes,Yes\n"
    )
    plan = tmp_path / "plan.csv"
    plan.write_text(
        "workstream,name,kind,duration_weeks,after,override\n"
        "a,m1,milestone,1,,\n"
        "a,long,task,30,m1,\n"
    )
    rc = sd.main(
        [
            "--breaks",
            str(breaks),
            "--school-year",
            "2026",
            "--regions",
            "Newark,Camden",
            "--start",
            "2027-01-11",
            "--plan",
            str(plan),
            "--end",
            "2027-06-18",
        ]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "| due |" in out
    assert "| m1 |" in out and "| long |" in out
    assert "after 2027-06-18" in out


# review fixes


def test_follower_of_thursday_due_row_starts_next_week():
    c = [sd.Closure(date(2027, 1, 15), date(2027, 1, 15), "x")]  # closed Friday
    out = sd.place(
        [
            sd.PlanRow("a", "m1", "milestone", 1),
            sd.PlanRow("a", "t1", "task", 1, after="m1"),
        ],
        date(2027, 1, 11),
        c,
        END,
    )
    assert (out[0].due, out[1].due) == (date(2027, 1, 14), date(2027, 1, 22))


def test_follower_of_midweek_override_starts_next_week(closures):
    out = sd.place(
        [
            sd.PlanRow("a", "m1", "milestone", 1, override=date(2027, 1, 13)),
            sd.PlanRow("a", "t1", "task", 1, after="m1"),
        ],
        date(2027, 1, 11),
        closures,
        END,
    )
    assert out[1].due == date(2027, 1, 22)


def test_closed_thursday_and_friday_moves_to_wednesday():
    c = [sd.Closure(date(2027, 1, 14), date(2027, 1, 15), "x")]  # Thu-Fri
    [p] = sd.place([sd.PlanRow("a", "m1", "milestone", 1)], date(2027, 1, 11), c, END)
    assert (p.due, p.rule) == (date(2027, 1, 13), "closed friday -> wednesday")


def test_zero_duration_rejected():
    with pytest.raises(ValueError, match="m1"):
        sd.place([sd.PlanRow("a", "m1", "milestone", 0)], date(2027, 1, 11), [], END)


def test_calendar_end_comes_from_every_region(tmp_path):
    breaks = tmp_path / "breaks.csv"
    breaks.write_text(
        "Month,Date,Day,Holiday/Event,Newark,Camden,Miami,Paterson\n"
        "November,27,Fri,x,Yes,Yes,Yes,Yes\n"
        "June,18,Fri,Juneteenth,No,Yes,No,No\n"
    )
    assert sd.calendar_end(breaks, 2026) == date(2027, 6, 18)


def test_cli_rejects_unknown_region(tmp_path, capsys):
    breaks = tmp_path / "breaks.csv"
    breaks.write_text("Month,Date,Day,Holiday/Event,Newark,Camden,Miami,Paterson\n")
    plan = tmp_path / "plan.csv"
    plan.write_text(
        "workstream,name,kind,duration_weeks,after,override\na,m1,milestone,1,,\n"
    )
    rc = sd.main(
        [
            "--breaks",
            str(breaks),
            "--school-year",
            "2026",
            "--regions",
            "newark",
            "--start",
            "2027-01-11",
            "--plan",
            str(plan),
        ]
    )
    assert rc == 2
    assert "newark" in capsys.readouterr().err


# PR review (bot) fixes


def test_split_rows_block_the_week():
    rows_ = [
        sd.Closure(
            date(2026, 12, 23), date(2026, 12, 24), "break", frozenset({"Newark"})
        ),
        sd.Closure(
            date(2026, 12, 25), date(2026, 12, 25), "holiday", frozenset({"Newark"})
        ),
    ]
    assert date(2026, 12, 21) in sd.blocked_weeks(rows_, [2026])


def test_single_day_rows_closing_a_whole_week_block_it():
    rows_ = [
        sd.Closure(
            date(2027, 3, 1 + i), date(2027, 3, 1 + i), "x", frozenset({"Miami"})
        )
        for i in range(5)
    ]
    assert date(2027, 3, 1) in sd.blocked_weeks(rows_, [2026])


def test_closed_days_in_different_regions_do_not_add_up():
    rows_ = [
        sd.Closure(
            date(2027, 3, 1), date(2027, 3, 1), "x", frozenset({"Camden"})
        ),  # Mon
        sd.Closure(
            date(2027, 3, 2), date(2027, 3, 3), "y", frozenset({"Miami"})
        ),  # Tue-Wed
    ]
    assert date(2027, 3, 1) not in sd.blocked_weeks(rows_, [2026])


def test_parse_breaks_keeps_in_scope_regions():
    [c] = sd.parse_breaks(
        rows(("November", "11", "Yes", "Yes", "No", "Yes")), 2026, ["Newark", "Miami"]
    )
    assert c.regions == frozenset({"Newark"})


def test_region_yes_with_trailing_space_counts():
    [c] = sd.parse_breaks(
        rows(("November", "11", "Yes ", "No", "No", "No")), 2026, ["Newark"]
    )
    assert c.start == date(2026, 11, 11)


def test_override_on_closed_day_is_noted(closures):
    [p] = sd.place(
        [sd.PlanRow("a", "m1", "milestone", 1, override=date(2027, 2, 18))],
        date(2027, 1, 11),
        closures,
        END,
    )
    assert "closed day" in p.note and "blocked week" in p.note


def test_override_before_predecessor_is_noted(closures):
    out = sd.place(
        [
            sd.PlanRow("a", "m1", "milestone", 2),
            sd.PlanRow("a", "t1", "task", 1, after="m1", override=date(2027, 1, 8)),
        ],
        date(2027, 1, 11),
        closures,
        END,
    )
    assert "before m1" in out[1].note


def test_read_plan_rejects_pipes(tmp_path):
    plan = tmp_path / "plan.csv"
    plan.write_text(
        "workstream,name,kind,duration_weeks,after,override\na,m|1,milestone,1,,\n"
    )
    with pytest.raises(ValueError, match="not allowed"):
        sd.read_plan(plan)


# second PR review


def test_split_row_break_moves_due_date_past_the_week():
    closures_ = sd.parse_breaks(
        rows(
            ("December", "23-24", "Yes", "Yes", "No", "Yes"),
            ("", "25", "Yes", "Yes", "Yes", "Yes"),
        ),
        2026,
        ["Newark"],
    )
    [p] = sd.place(
        [sd.PlanRow("a", "m1", "milestone", 1)],
        date(2026, 12, 21),
        closures_,
        date(2027, 6, 18),
    )
    assert (p.due, p.rule) == (date(2027, 1, 1), "friday")  # week of 12/21 blocked


def test_union_of_regions_closing_every_weekday_blocks():
    rows_ = [
        sd.Closure(date(2027, 3, 1), date(2027, 3, 2), "x", frozenset({"Newark"})),
        sd.Closure(date(2027, 3, 3), date(2027, 3, 3), "y", frozenset({"Miami"})),
        sd.Closure(date(2027, 3, 4), date(2027, 3, 5), "z", frozenset({"Camden"})),
    ]
    assert date(2027, 3, 1) in sd.blocked_weeks(rows_, [2026])


def test_four_closed_days_across_regions_leave_a_monday_due_date():
    rows_ = [
        sd.Closure(
            date(2027, 3, 2), date(2027, 3, 3), "x", frozenset({"Miami"})
        ),  # Tue-Wed
        sd.Closure(
            date(2027, 3, 4), date(2027, 3, 5), "y", frozenset({"Newark"})
        ),  # Thu-Fri
    ]
    [p] = sd.place(
        [sd.PlanRow("a", "m1", "milestone", 1)], date(2027, 3, 1), rows_, END
    )
    assert (p.due, p.rule) == (date(2027, 3, 1), "closed friday -> monday")


def test_clean_override_note_is_exactly_override(closures):
    [p] = sd.place(
        [sd.PlanRow("a", "m1", "milestone", 1, override=date(2027, 1, 15))],
        date(2027, 1, 11),
        closures,
        END,
    )
    assert p.note == "override"


def test_override_in_blocked_week_only_is_noted(closures):
    [p] = sd.place(
        [sd.PlanRow("a", "m1", "milestone", 1, override=date(2027, 2, 16))],
        date(2027, 1, 11),
        closures,
        END,
    )
    assert p.note == "override (blocked week)"


def test_override_on_weekend_is_noted(closures):
    [p] = sd.place(
        [sd.PlanRow("a", "m1", "milestone", 1, override=date(2027, 1, 16))],
        date(2027, 1, 11),
        closures,
        END,
    )
    assert "weekend" in p.note


def test_override_before_project_start_is_noted(closures):
    [p] = sd.place(
        [sd.PlanRow("a", "m1", "milestone", 1, override=date(2027, 1, 8))],
        date(2027, 1, 11),
        closures,
        END,
    )
    assert "before start" in p.note


def test_override_equal_to_predecessor_says_on_or_before(closures):
    out = sd.place(
        [
            sd.PlanRow("a", "m1", "milestone", 1),
            sd.PlanRow("a", "t1", "task", 1, after="m1", override=date(2027, 1, 15)),
        ],
        date(2027, 1, 11),
        closures,
        END,
    )
    assert "on or before m1" in out[1].note

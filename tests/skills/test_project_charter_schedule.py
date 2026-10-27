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

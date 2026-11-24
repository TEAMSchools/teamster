"""Place a service playbook's steps in weeks and total its hours by month.

Placement:

- A step starts at its round's open or close week (``anchor``). Offset 0 is
  that week even when it is blocked: window weeks are never moved.
- A nonzero offset moves that many unblocked weeks forward or back. Blocked
  weeks are skipped and do not count.
- The week reached is the step's first week. Each further week, up to
  ``duration_weeks``, is the next unblocked week after the one before.

Blocking, for a network-wide workstream: a week is blocked only when every
region blocks it, by the rules in project-charter's ``schedule_dates.py``.

Hours: a week counts in the month of its Monday, and months run July to June.
Standing work with ``weeks: school_year`` covers the unblocked Mondays from
``first_week`` to ``last_week``; ``weeks: all`` covers every Monday of the
school year. A step week outside the school year is an error, never dropped.

The spec JSON and the output shape are described in
``references/playbook-doc.md``.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import importlib.util
import json
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, Literal, Sequence


def _load_schedule_dates():
    name = "schedule_dates"
    if name in sys.modules:
        return sys.modules[name]
    path = (
        Path(__file__).resolve().parents[2]
        / "project-charter"
        / "scripts"
        / "schedule_dates.py"
    )
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sd = _load_schedule_dates()

WEEK = timedelta(days=7)


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


@dataclass(frozen=True)
class Window:
    round_key: str
    open_week: date
    close_week: date

    def __post_init__(self) -> None:
        object.__setattr__(self, "open_week", _monday(self.open_week))
        object.__setattr__(self, "close_week", _monday(self.close_week))
        if self.close_week < self.open_week:
            raise ValueError(f"round {self.round_key!r}: closes before it opens")


@dataclass(frozen=True)
class Step:
    name: str
    anchor: Literal["open", "close"]
    offset_weeks: int
    duration_weeks: int
    hours_per_week: float
    role: str
    rounds: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if self.anchor not in ("open", "close"):
            raise ValueError(f"step {self.name!r}: anchor must be open or close")
        if self.duration_weeks < 1:
            raise ValueError(f"step {self.name!r}: duration_weeks must be at least 1")
        if self.hours_per_week < 0:
            raise ValueError(f"step {self.name!r}: hours_per_week is negative")


@dataclass(frozen=True)
class Standing:
    name: str
    hours_per_week: float
    weeks: Literal["school_year", "all"]

    def __post_init__(self) -> None:
        if self.weeks not in ("school_year", "all"):
            raise ValueError(
                f"standing {self.name!r}: weeks must be school_year or all"
            )


def network_blocked(closures: Iterable, years: Iterable[int]) -> frozenset[date]:
    """Mondays every region blocks. A closure with no regions counts for all."""
    closures, years = list(closures), list(years)
    result: frozenset[date] | None = None
    for region in sd.REGIONS:
        mine = [
            dataclasses.replace(c, regions=frozenset({region}))
            for c in closures
            if not c.regions or region in c.regions
        ]
        weeks = sd.blocked_weeks(mine, years)
        result = weeks if result is None else result & weeks
    return result or frozenset()


def _shift(week: date, n: int, blocked: frozenset[date]) -> date:
    step = WEEK if n > 0 else -WEEK
    remaining = abs(n)
    while remaining:
        week += step
        if week not in blocked:
            remaining -= 1
    return week


def step_weeks(step: Step, window: Window, blocked: frozenset[date]) -> list[date]:
    """Mondays the step occupies in one round."""
    week = window.open_week if step.anchor == "open" else window.close_week
    if step.offset_weeks:
        week = _shift(week, step.offset_weeks, blocked)
    weeks = [week]
    while len(weeks) < step.duration_weeks:
        weeks.append(_shift(weeks[-1], 1, blocked))
    return weeks


def _school_year(school_year_start: int) -> tuple[date, date]:
    return date(school_year_start, 7, 1), date(school_year_start + 1, 6, 30)


def _month_index(week: date) -> int:
    return (week.month - 7) % 12


def placed_steps(
    steps: Sequence[Step], windows: Sequence[Window], blocked: frozenset[date]
) -> list[tuple[Step, Window, list[date]]]:
    """Every (step, round, weeks) the playbook produces, in step order."""
    by_key: dict[str, Window] = {}
    for w in windows:
        if w.round_key in by_key:
            raise ValueError(f"round {w.round_key!r} has two windows")
        by_key[w.round_key] = w
    out = []
    for step in steps:
        keys = step.rounds if step.rounds is not None else tuple(by_key)
        for key in keys:
            if key not in by_key:
                raise ValueError(f"step {step.name!r}: round {key!r} has no window")
            out.append((step, by_key[key], step_weeks(step, by_key[key], blocked)))
    return out


def monthly_hours(
    steps: Sequence[Step],
    windows: Sequence[Window],
    standing: Sequence[Standing],
    blocked: frozenset[date],
    school_year_start: int,
    first_week: date,
    last_week: date,
) -> list[float]:
    """Hours per month, July first, 12 values."""
    year_first, year_last = _school_year(school_year_start)
    hours = [0.0] * 12
    for step, window, weeks in placed_steps(steps, windows, blocked):
        for week in weeks:
            if not year_first <= week <= year_last:
                raise ValueError(
                    f"step {step.name!r} in round {window.round_key!r}: week of "
                    f"{week} is outside the {school_year_start}-"
                    f"{school_year_start + 1} school year"
                )
            hours[_month_index(week)] += step.hours_per_week
    for item in standing:
        if item.weeks == "all":
            week, end, skip = _monday(year_first), year_last, frozenset()
            if week < year_first:
                week += WEEK
        else:
            week, end, skip = _monday(first_week), last_week, blocked
        while week <= end:
            if week not in skip:
                hours[_month_index(week)] += item.hours_per_week
            week += WEEK
    return hours


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Place playbook steps in weeks and total hours by month."
    )
    p.add_argument("--spec", required=True, type=Path, help="playbook JSON")
    p.add_argument("--breaks", required=True, type=Path, help="breaks tab as CSV")
    p.add_argument("--school-year", required=True, type=int, help="year it starts")
    p.add_argument("--first-week", required=True, type=date.fromisoformat)
    p.add_argument("--last-week", required=True, type=date.fromisoformat)
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        spec = json.loads(args.spec.read_text())
        windows = [
            Window(
                w["round_key"],
                date.fromisoformat(w["open_week"]),
                date.fromisoformat(w["close_week"]),
            )
            for w in spec.get("windows", [])
        ]
        steps = [
            Step(**{**s, "rounds": tuple(s["rounds"]) if s.get("rounds") else None})
            for s in spec.get("steps", [])
        ]
        standing = [Standing(**s) for s in spec.get("standing", [])]
        with args.breaks.open(newline="") as f:
            closures = sd.parse_breaks(csv.DictReader(f), args.school_year, sd.REGIONS)
        blocked = network_blocked(closures, [args.school_year])
        hours = monthly_hours(
            steps,
            windows,
            standing,
            blocked,
            args.school_year,
            args.first_week,
            args.last_week,
        )
        placed = placed_steps(steps, windows, blocked)
    except (KeyError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "steps": [
                    {
                        "round": w.round_key,
                        "step": s.name,
                        "weeks": [d.isoformat() for d in weeks],
                    }
                    for s, w, weeks in placed
                ],
                "hours_by_month": [round(h, 2) for h in hours],
                "hours_per_year": round(sum(hours), 2),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

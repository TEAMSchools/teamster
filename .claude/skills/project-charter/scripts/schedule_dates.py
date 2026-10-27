"""Place work-plan due dates around the network's regional breaks.

Rules, applied in this order:

- Due dates are Fridays.
- A week is blocked when any in-scope region has a closure of 3 or more
  consecutive weekdays in it. Blocked weeks are skipped and do not count
  toward a duration. A single closed day does not block its week.
- Thanksgiving week is blocked whatever the breaks tab says.
- A Friday that is a closed day for any in-scope region moves to Thursday.
- A due date past the last closure in the breaks table is marked
  ``unverified: calendar not published``.

The breaks table is the "Important Dates/Federal Holidays" tab of the network
calendar sheet, exported to CSV with its headers unchanged; its shape and the
plan CSV are described in ``references/scheduling.md``.
"""

from __future__ import annotations

import argparse
import calendar
import csv
import re
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, Mapping, Sequence

REGIONS = ("Newark", "Camden", "Miami", "Paterson")

_MONTHS = {
    **{name.lower(): i for i, name in enumerate(calendar.month_name) if name},
    **{abbr.lower(): i for i, abbr in enumerate(calendar.month_abbr) if abbr},
}
_PART = re.compile(r"^\s*(?:([A-Za-z]+)\.?\s+)?(\d{1,2})\s*(?:\(([A-Za-z]+)\.?\))?\s*$")


@dataclass(frozen=True)
class Closure:
    start: date
    end: date  # inclusive
    name: str


def _month_number(name: str) -> int:
    try:
        return _MONTHS[name.strip().lower()]
    except KeyError:
        raise ValueError(f"unknown month {name!r}") from None


def _year_for(month: int, school_year_start: int) -> int:
    return school_year_start if month >= 7 else school_year_start + 1


def _parse_part(part: str, default_month: int, school_year_start: int) -> date:
    m = _PART.match(part)
    if not m:
        raise ValueError(f"cannot parse {part!r}")
    named = m.group(1) or m.group(3)
    month = _month_number(named) if named else default_month
    return date(_year_for(month, school_year_start), month, int(m.group(2)))


def parse_breaks(
    rows: Iterable[Mapping[str, str]],
    school_year_start: int,
    regions: Sequence[str],
) -> list[Closure]:
    """Closures from the breaks tab for the regions in scope.

    A row counts when any in-scope region column is exactly ``Yes``. July to
    December take ``school_year_start``; January to June the year after. A
    ``Date`` of ``21 - 1`` whose end day is below its start crosses into the
    next month; a cell naming months (``Dec 21 - Jan 1``, ``29-2 (Apr)``) uses
    those. A blank ``Month`` continues the row above.
    """
    closures: list[Closure] = []
    current_month = ""
    for row in rows:
        current_month = (row.get("Month") or "").strip() or current_month
        if not any(row.get(region) == "Yes" for region in regions):
            continue
        label = f"Month={current_month!r} Date={row.get('Date')!r} Holiday/Event={row.get('Holiday/Event')}"
        try:
            month = _month_number(current_month)
            parts = [p for p in re.split(r"\s*[-–]\s*", row["Date"].strip()) if p]
            if not parts or len(parts) > 2:
                raise ValueError(f"cannot parse {row['Date']!r}")
            start = _parse_part(parts[0], month, school_year_start)
            end = start
            if len(parts) == 2:
                end = _parse_part(parts[1], start.month, school_year_start)
                if end < start:
                    nxt = start.month % 12 + 1
                    end = date(_year_for(nxt, school_year_start), nxt, end.day)
        except (KeyError, ValueError) as exc:
            raise ValueError(f"breaks row {label}: {exc}") from None
        closures.append(Closure(start, end, row.get("Holiday/Event", "")))
    return closures


def thanksgiving(year: int) -> date:
    """Fourth Thursday of November."""
    first = date(year, 11, 1)
    offset = (calendar.THURSDAY - first.weekday()) % 7
    return first.replace(day=1 + offset + 21)


def _weekdays(closure: Closure) -> list[date]:
    days = []
    d = closure.start
    while d <= closure.end:
        if d.weekday() < 5:
            days.append(d)
        d = d.fromordinal(d.toordinal() + 1)
    return days


def _monday(d: date) -> date:
    return d.fromordinal(d.toordinal() - d.weekday())


def closed_days(closures: Iterable[Closure]) -> frozenset[date]:
    """Every weekday inside any closure."""
    return frozenset(d for c in closures for d in _weekdays(c))


def blocked_weeks(closures: Iterable[Closure], years: Iterable[int]) -> frozenset[date]:
    """Mondays of blocked weeks: 3+ weekdays closed by one closure, plus
    Thanksgiving week of every year given. Two closures do not add up."""
    blocked = {_monday(thanksgiving(y)) for y in years}
    for c in closures:
        per_week: dict[date, int] = {}
        for d in _weekdays(c):
            per_week[_monday(d)] = per_week.get(_monday(d), 0) + 1
        blocked.update(week for week, n in per_week.items() if n >= 3)
    return frozenset(blocked)


UNVERIFIED = "unverified: calendar not published"


@dataclass(frozen=True)
class PlanRow:
    workstream: str
    name: str
    kind: str  # "milestone" or "task"
    duration_weeks: int  # >= 1
    after: str | None = None  # another row's name
    override: date | None = None


@dataclass(frozen=True)
class Placed:
    row: PlanRow
    due: date
    rule: str
    note: str


def _place_one(
    row: PlanRow, start: date, blocked: frozenset[date], closed: frozenset[date]
) -> tuple[date, str]:
    week = _monday(start) if start.weekday() < 5 else _monday(start + timedelta(days=7))
    remaining = row.duration_weeks
    while True:
        if week not in blocked:
            remaining -= 1
            if remaining == 0:
                break
        week += timedelta(days=7)
    friday = week + timedelta(days=4)
    if friday in closed:
        return friday - timedelta(days=1), "closed friday -> thursday"
    return friday, "friday"


def place(
    rows: Sequence[PlanRow],
    start: date,
    closures: Iterable[Closure],
    calendar_end: date,
) -> list[Placed]:
    """Date every row. A row with no ``after`` starts at ``start``; one with
    an ``after`` starts the Monday after its predecessor's due date. An
    ``override`` replaces the computed date and followers start from it."""
    closures = list(closures)
    years = {start.year, start.year + 1, *(c.start.year for c in closures)}
    blocked = blocked_weeks(closures, years)
    closed = closed_days(closures)
    names = [r.name for r in rows]
    if len(set(names)) != len(names):
        raise ValueError(f"duplicate row names in {names}")
    placed: dict[str, Placed] = {}
    pending = list(rows)
    while pending:
        progressed = False
        for row in list(pending):
            if row.after is not None and row.after not in placed:
                continue
            row_start = (
                start
                if row.after is None
                else placed[row.after].due + timedelta(days=1)
            )
            if row.override is not None:
                due, rule, note = row.override, "override", "override"
            else:
                due, rule = _place_one(row, row_start, blocked, closed)
                note = ""
            if due > calendar_end:
                note = UNVERIFIED if not note else f"{note}; {UNVERIFIED}"
            placed[row.name] = Placed(row, due, rule, note)
            pending.remove(row)
            progressed = True
        if not progressed:
            unknown = sorted(
                {r.after for r in pending if r.after not in names or r.after == r.name}
            )
            raise ValueError(
                f"rows {[r.name for r in pending]} wait on {unknown or 'a cycle'}; known rows: {names}"
            )
    return [placed[n] for n in names]


def read_plan(path: Path) -> list[PlanRow]:
    """Plan CSV: workstream,name,kind,duration_weeks,after,override."""
    out = []
    with path.open(newline="") as fh:
        for r in csv.DictReader(fh):
            out.append(
                PlanRow(
                    workstream=r["workstream"],
                    name=r["name"],
                    kind=r["kind"],
                    duration_weeks=int(r["duration_weeks"]),
                    after=r.get("after") or None,
                    override=date.fromisoformat(r["override"])
                    if r.get("override")
                    else None,
                )
            )
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--breaks", type=Path, required=True, help="breaks tab as CSV")
    ap.add_argument(
        "--school-year", type=int, required=True, help="start year of the school year"
    )
    ap.add_argument(
        "--regions", required=True, help="comma-separated, from " + ",".join(REGIONS)
    )
    ap.add_argument("--start", type=date.fromisoformat, required=True)
    ap.add_argument("--plan", type=Path, required=True, help="plan rows as CSV")
    ap.add_argument(
        "--end", type=date.fromisoformat, help="target end date from the charter"
    )
    a = ap.parse_args(argv)
    try:
        with a.breaks.open(newline="") as fh:
            closures = parse_breaks(
                csv.DictReader(fh), a.school_year, a.regions.split(",")
            )
        calendar_end = max(c.end for c in closures)
        placed = place(read_plan(a.plan), a.start, closures, calendar_end)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    print("| workstream | name | kind | due | rule | note |")
    print("| --- | --- | --- | --- | --- | --- |")
    for p in placed:
        print(
            f"| {p.row.workstream} | {p.row.name} | {p.row.kind} | {p.due} | {p.rule} | {p.note} |"
        )
    if a.end:
        late = [p.row.name for p in placed if p.due > a.end]
        if late:
            print(f"\nRows due after {a.end}: {', '.join(late)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

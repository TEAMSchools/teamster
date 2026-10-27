"""Place work-plan due dates around the network's regional breaks.

Rules, applied in this order:

- Due dates are Fridays.
- A week is blocked when any in-scope region has 3 or more consecutive
  closed weekdays in it, counted across every row of the breaks table, or
  when no weekday is open in any in-scope region. Blocked weeks are skipped
  and do not count toward a duration. A single closed day does not block its
  week, and closed days in different regions do not add up.
- Thanksgiving week is blocked whatever the breaks tab says.
- A Friday that is a closed day for any in-scope region moves back to the
  nearest open day of its week.
- An override is placed as given and noted when it falls on a closed day, in
  a blocked week, or before the row it follows.
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
    regions: frozenset[str] = frozenset()  # in-scope regions closed; empty = all


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

    A row counts when any in-scope region column is ``Yes`` (surrounding
    whitespace ignored, case not); those regions go on the closure. July to
    December take ``school_year_start``; January to June the year after. A
    ``Date`` of ``21 - 1`` whose end day is below its start crosses into the
    next month; a cell naming months (``Dec 21 - Jan 1``, ``29-2 (Apr)``) uses
    those. A blank ``Month`` continues the row above.
    """
    closures: list[Closure] = []
    current_month = ""
    for row in rows:
        current_month = (row.get("Month") or "").strip() or current_month
        closed_in = frozenset(r for r in regions if (row.get(r) or "").strip() == "Yes")
        if not closed_in:
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
        closures.append(Closure(start, end, row.get("Holiday/Event", ""), closed_in))
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


def _longest_run(offsets: set[int]) -> int:
    run = best = 0
    for i in range(5):
        run = run + 1 if i in offsets else 0
        best = max(best, run)
    return best


def blocked_weeks(closures: Iterable[Closure], years: Iterable[int]) -> frozenset[date]:
    """Mondays of blocked weeks: a region with 3+ consecutive closed weekdays,
    counted across rows; a week with no open weekday in any region; and
    Thanksgiving week of every year given. A closure with no regions counts
    for every region."""
    blocked = {_monday(thanksgiving(y)) for y in years}
    per_region: dict[str, dict[date, set[int]]] = {}
    union: dict[date, set[int]] = {}
    for c in closures:
        for d in _weekdays(c):
            week, offset = _monday(d), d.weekday()
            union.setdefault(week, set()).add(offset)
            for region in c.regions or {"*"}:
                per_region.setdefault(region, {}).setdefault(week, set()).add(offset)
    for weeks in per_region.values():
        blocked.update(
            week for week, offsets in weeks.items() if _longest_run(offsets) >= 3
        )
    blocked.update(week for week, offsets in union.items() if len(offsets) == 5)
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
    due = friday
    while due in closed and due > week:
        due -= timedelta(days=1)
    if due != friday:
        return due, f"closed friday -> {calendar.day_name[due.weekday()].lower()}"
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
    short = [r.name for r in rows if r.duration_weeks < 1]
    if short:
        raise ValueError(f"duration_weeks must be at least 1: {short}")
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
                else _monday(placed[row.after].due) + timedelta(days=7)
            )
            if row.override is not None:
                due, rule = row.override, "override"
                warnings = []
                if due in closed:
                    warnings.append("closed day")
                if _monday(due) in blocked:
                    warnings.append("blocked week")
                if row.after is not None and due <= placed[row.after].due:
                    warnings.append(f"before {row.after}")
                note = "override" + (f" ({', '.join(warnings)})" if warnings else "")
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
                {
                    r.after
                    for r in pending
                    if r.after is not None
                    and (r.after not in names or r.after == r.name)
                }
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
            try:
                if "|" in r["workstream"] + r["name"]:
                    raise ValueError("'|' is not allowed in workstream or name")
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
            except ValueError as exc:
                raise ValueError(f"plan row {r.get('name')!r}: {exc}") from None
    return out


def calendar_end(path: Path, school_year: int) -> date:
    """The last closure date in the breaks table for any region, so the
    unverified marker does not depend on the regions in scope."""
    with path.open(newline="") as fh:
        ends = [c.end for c in parse_breaks(csv.DictReader(fh), school_year, REGIONS)]
    if not ends:
        raise ValueError(
            f"no closures in {path}; is it the breaks table with its header row?"
        )
    return max(ends)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
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
        regions = a.regions.split(",")
        bad = [r for r in regions if r not in REGIONS]
        if bad:
            raise ValueError(f"unknown regions {bad}; use {', '.join(REGIONS)}")
        with a.breaks.open(newline="") as fh:
            closures = parse_breaks(csv.DictReader(fh), a.school_year, regions)
        placed = place(
            read_plan(a.plan), a.start, closures, calendar_end(a.breaks, a.school_year)
        )
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

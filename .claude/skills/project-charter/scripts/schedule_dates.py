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

import calendar
import re
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Mapping, Sequence

REGIONS = ("Newark", "Camden", "Miami", "Paterson")

_MONTHS = {
    **{name.lower(): i for i, name in enumerate(calendar.month_name) if name},
    **{abbr.lower(): i for i, abbr in enumerate(calendar.month_abbr) if abbr},
}
_PART = re.compile(r"^\s*(?:([A-Za-z]+)\.?\s+)?(\d{1,2})\s*$")


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
    month = _month_number(m.group(1)) if m.group(1) else default_month
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
    next month; a cell naming months (``Dec 21 - Jan 1``) uses those.
    """
    closures: list[Closure] = []
    for row in rows:
        if not any(row.get(region) == "Yes" for region in regions):
            continue
        label = f"Month={row.get('Month')!r} Date={row.get('Date')!r} Holiday/Event={row.get('Holiday/Event')}"
        try:
            month = _month_number(row["Month"])
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

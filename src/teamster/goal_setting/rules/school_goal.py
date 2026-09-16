"""School goal strategies.

bubble_parameter: the production method. One parameter per region and grade
spreads the region target across schools in proportion to each school's
approaching students. blanket: every school gets the region target.
"""

from __future__ import annotations

import math

from teamster.goal_setting.records import SchoolGoal
from teamster.goal_setting.rules.aggregate import SchoolCounts

Targets = dict[tuple[str, int], float]  # (region, grade_level) -> proportion


class MissingTarget(ValueError):
    pass


def _target(targets: Targets, c: SchoolCounts) -> float:
    try:
        return targets[(c.region, c.grade_level)]
    except KeyError as e:
        raise MissingTarget(
            f"no target for {c.region} grade {c.grade_level} {c.subject}"
        ) from e


def region_parameters(
    counts: list[SchoolCounts], targets: Targets
) -> dict[tuple[str, int], float | None]:
    acc: dict[tuple[str, int], list[int]] = {}
    for c in counts:
        t = acc.setdefault((c.region, c.grade_level), [0, 0, 0])
        t[0] += c.n_tested
        t[1] += c.n_proficient
        t[2] += c.n_approaching
    out: dict[tuple[str, int], float | None] = {}
    for key, (tested, prof, appr) in acc.items():
        target = targets.get(key)
        if target is None:
            raise MissingTarget(f"no target for {key[0]} grade {key[1]}")
        out[key] = None if appr == 0 else round((tested * target - prof) / appr, 2)
    return out


def _goal(c: SchoolCounts, n_to_move: int) -> float:
    return (
        0.0 if c.n_tested == 0 else round((c.n_proficient + n_to_move) / c.n_tested, 2)
    )


def bubble_parameter(counts: list[SchoolCounts], targets: Targets) -> list[SchoolGoal]:
    params = region_parameters(counts, targets)
    out = []
    for c in counts:
        bp = params[(c.region, c.grade_level)]
        # round before ceil: 25 * 0.36 is 9.000000000000002 in float64
        n_to_move = (
            0 if bp is None else max(0, math.ceil(round(c.n_approaching * bp, 6)))
        )
        out.append(
            SchoolGoal(
                region=c.region,
                school=c.school,
                school_id=c.school_id,
                grade_level=c.grade_level,
                subject=c.subject,
                n_roster=c.n_roster,
                n_tested=c.n_tested,
                n_proficient=c.n_proficient,
                n_approaching=c.n_approaching,
                n_below=c.n_below,
                target=_target(targets, c),
                bubble_parameter=bp,
                n_to_move=n_to_move,
                goal=_goal(c, n_to_move),
            )
        )
    return out


def blanket(counts: list[SchoolCounts], targets: Targets) -> list[SchoolGoal]:
    out = []
    for c in counts:
        target = _target(targets, c)
        # round before ceil: 0.55 * 20 is 11.000000000000002 in float64
        n_to_move = max(0, math.ceil(round(target * c.n_tested - c.n_proficient, 6)))
        out.append(
            SchoolGoal(
                region=c.region,
                school=c.school,
                school_id=c.school_id,
                grade_level=c.grade_level,
                subject=c.subject,
                n_roster=c.n_roster,
                n_tested=c.n_tested,
                n_proficient=c.n_proficient,
                n_approaching=c.n_approaching,
                n_below=c.n_below,
                target=target,
                bubble_parameter=None,
                n_to_move=n_to_move,
                goal=target,
            )
        )
    return out

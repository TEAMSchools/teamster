"""Completeness gate. Runs between fetch and compute.

A half-loaded upstream and a small group look identical to the rules and both
land every student in Bucket 4. This gate compares what was fetched against a
baseline and a tested-share floor before any rule runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from teamster.goal_setting.config import Freshness
from teamster.goal_setting.rules.aggregate import SchoolCounts

Baseline = dict[tuple[str, str, int], int]  # (region, school, grade) -> roster count


@dataclass
class GateResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def check(
    counts: list[SchoolCounts], cfg: Freshness, baseline: Baseline | None
) -> GateResult:
    res = GateResult()
    if not counts:
        res.errors.append("roster fetch returned 0 rows")
        return res

    subject = counts[0].subject

    for c in counts:
        where = f"{c.region} {c.school} grade {c.grade_level} {c.subject}"
        share = 0.0 if c.n_roster == 0 else c.n_tested / c.n_roster
        if share < cfg.min_tested_share:
            res.errors.append(
                f"{where}: tested share {share:.2f} is below floor "
                f"{cfg.min_tested_share:.2f} ({c.n_tested} of {c.n_roster})"
            )
        if baseline is not None:
            base = baseline.get((c.region, c.school, c.grade_level))
            if base is None:
                res.warnings.append(
                    f"{where}: no baseline row; {c.n_roster} students fetched"
                )
                continue
            low = round(base * (1 - cfg.roster_tolerance), 6)
            high = round(base * (1 + cfg.roster_tolerance), 6)
            if c.n_roster < low:
                res.errors.append(
                    f"{where}: roster {c.n_roster} is below baseline {base} "
                    f"minus {cfg.roster_tolerance:.0%}"
                )
            elif c.n_roster > high:
                res.warnings.append(
                    f"{where}: roster {c.n_roster} is above baseline {base} "
                    f"plus {cfg.roster_tolerance:.0%}"
                )

    if baseline is None:
        res.warnings.append(
            "no baseline available; roster counts were not compared to a prior run"
        )
    else:
        fetched = {(c.region, c.school, c.grade_level) for c in counts}
        for (region, school, grade), base in sorted(baseline.items()):
            if (region, school, grade) not in fetched:
                res.errors.append(
                    f"{region} {school} grade {grade} {subject}: 0 students "
                    f"fetched, baseline {base}"
                )
    return res

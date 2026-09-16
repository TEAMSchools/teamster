"""Assemble one group's proposal. Pure: takes records, returns a Proposal."""

from __future__ import annotations

import importlib
from dataclasses import dataclass

from teamster.goal_setting.config import STRATEGIES, Group
from teamster.goal_setting.records import SchoolGoal, StudentRecord
from teamster.goal_setting.rules import assign, classify, freshness, invariants
from teamster.goal_setting.rules.aggregate import count_by_school
from teamster.goal_setting.rules.freshness import Baseline, GateResult

Targets = dict[tuple[str, int], float]


class FreshnessError(Exception):
    pass


@dataclass
class Proposal:
    group: Group
    academic_year: int
    records: list[StudentRecord]
    goals: list[SchoolGoal]
    targets: Targets
    gate: GateResult


def resolve(slot: str, name: str):
    path = STRATEGIES[slot][name]
    if path is None:
        raise NotImplementedError(
            f"{slot} strategy '{name}' is not implemented yet; planned for a "
            "later PR (see the design spec's rollout order)"
        )
    module, _, attr = path.partition(":")
    return getattr(importlib.import_module(module), attr)


def run_group(
    group: Group,
    academic_year: int,
    records: list[StudentRecord],
    targets: Targets,
    baseline: Baseline | None,
    force_stale: bool = False,
) -> Proposal:
    gate = freshness.check(count_by_school(records), group.freshness, baseline)
    if gate.errors and not force_stale:
        raise FreshnessError("\n".join(gate.errors))

    recs = classify.classify(records, group.levels)
    counts = count_by_school(recs)
    goals = resolve("school_goal", group.school_goal)(counts, targets)
    recs = resolve("bucket2", group.bucket2.strategy)(recs, goals, group.bucket2.ties)
    recs = resolve("bucket3", group.bucket3.strategy)(recs, group.levels)
    recs = assign.finalize(recs)
    invariants.check(recs, goals, targets, group.school_goal)
    return Proposal(group, academic_year, recs, goals, targets, gate)

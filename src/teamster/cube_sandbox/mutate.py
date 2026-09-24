"""Measure whether the canaries are load-bearing.

Perturb one access_policy block or one persona's scope value and require at
least one canary to flip red. A canary that would still pass with the policy
deleted proves nothing, and a suite of those is worse than none: it reports
confidence nobody has earned. This is the only honest measure of the suite.
"""

from __future__ import annotations

from typing import Any


def uncaught_ratio(results: list[bool]) -> float:
    """The share of mutations no canary caught. `True` means caught."""
    return 0.0 if not results else sum(1 for r in results if not r) / len(results)


def uncaught(mutations: dict[str, bool]) -> list[str]:
    """Which mutations went uncaught, named so they can be fixed.

    A bare percentage says how bad it is; this says where. An uncaught
    mutation names a policy or a persona scope that no canary actually
    exercises.
    """
    return sorted(name for name, caught in mutations.items() if not caught)


def report(mutations: dict[str, bool]) -> dict[str, Any]:
    """The run's result, with the empty case unmistakable.

    A run that mutated nothing used to print `uncaught_ratio: 0.0` — which
    reads as a perfect score on a report nobody can tell apart from a real
    one. `exit_code` failed it correctly, but the two travel separately: the
    JSON is what gets attached to a kit release. So an empty run reports a
    null ratio and says in words that nothing was measured.
    """
    results = list(mutations.values())
    if not results:
        return {
            "mutations": 0,
            "uncaught": [],
            "uncaught_ratio": None,
            "verdict": (
                "NOT MEASURED: no mutation was applied, so this run says "
                "nothing about whether the canaries are load-bearing"
            ),
        }
    ratio = uncaught_ratio(results)
    return {
        "mutations": len(results),
        "uncaught": uncaught(mutations),
        "uncaught_ratio": ratio,
        "verdict": f"{len(uncaught(mutations))} of {len(results)} mutations uncaught",
    }


def exit_code(mutations: dict[str, bool], threshold: float = 0.0) -> int:
    """Non-zero when too many mutations went uncaught.

    The default threshold is zero: every mutation must be caught. A suite
    that tolerates a surviving mutant tolerates a policy nothing tests, and
    the spec asks for at least one canary to flip red for EACH perturbation.
    A run with no mutations at all fails too — an empty measurement is not a
    passing one.
    """
    if not mutations:
        return 1
    return 1 if uncaught_ratio(list(mutations.values())) > threshold else 0

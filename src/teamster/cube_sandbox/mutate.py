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
    results = list(mutations.values())
    return {
        "mutations": len(results),
        "uncaught": uncaught(mutations),
        "uncaught_ratio": uncaught_ratio(results),
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

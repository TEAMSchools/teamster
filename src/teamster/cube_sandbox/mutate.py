"""Measure whether the canaries are load-bearing.

Perturb one access_policy block or one persona's scope value and require at
least one canary to flip red. A canary that would still pass with the policy
deleted proves nothing, and a suite of those is worse than none: it reports
confidence nobody has earned. This is the only honest measure of the suite.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

CUBE_ROOT = Path("src/cube")
CANARIES_PATH = CUBE_ROOT / "sandbox" / "canaries.yml"
MATRIX_RUNNER = Path("scripts/cube_rls_matrix.py")

# The schema directory the Cube under test is serving. A mutation is applied
# by rewriting a file there and letting Cube's own watcher recompile; there
# is no API for "serve this model instead", and a mutation applied anywhere
# else measures nothing.
MODEL_DIR = "CUBE_SANDBOX_MODEL_DIR"
SQL_HOST = "CUBE_SANDBOX_SQL_HOST"
SQL_PORT = "CUBE_SANDBOX_SQL_PORT"
# trunk-ignore(bandit/B105): the NAME of a variable to read, not a value
SQL_PASSWORD = "CUBE_SANDBOX_SQL_PASSWORD"

# Seconds to let Cube notice a schema file changed and recompile. Too short
# and every mutation scores "uncaught" because the old model was still being
# served, which is the failure mode that would quietly invert this report.
RELOAD_SECONDS = 15.0


@dataclass(frozen=True)
class Mutation:
    """One perturbation: this file, rewritten this way."""

    name: str
    relative_path: Path
    mutated_text: str


def policy_mutations(cube_root: Path = CUBE_ROOT) -> list[Mutation]:
    """One mutation per `access_policy` block: delete it.

    Deleting a policy is the perturbation the spec asks for, and it is the
    one that matters: a canary that still passes with its policy deleted
    proves nothing, and a suite of those reports confidence nobody earned.

    Only the DEPLOYED MODEL is perturbed here. The spec's other arm —
    perturbing a persona's scope value — changes `dim_staff_cube_access`,
    which reaches a deployment only through a regenerate, a reload and the
    expiry of `resolveAccess`'s per-email cache at the next midnight ET.
    That is a cycle, not a mutation run, so this runner does not drive it
    and does not pretend to have scored it.
    """
    out = []
    for path in sorted((cube_root / "model" / "views").rglob("*.yml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        views = doc.get("views", [])
        for view_index, view in enumerate(views):
            for policy_index, policy in enumerate(view.get("access_policy", [])):
                mutated = yaml.safe_load(path.read_text(encoding="utf-8"))
                del mutated["views"][view_index]["access_policy"][policy_index]
                out.append(
                    Mutation(
                        name=f"drop {view.get('name')} policy "
                        f"{policy.get('role', policy_index)}",
                        relative_path=path.relative_to(cube_root),
                        mutated_text=yaml.safe_dump(mutated, sort_keys=False),
                    )
                )
    return out


def run(
    mutations: list[Mutation],
    model_dir: Path,
    canaries: Callable[[], int],
    settle: float = RELOAD_SECONDS,
) -> dict[str, bool]:
    """Apply each mutation in turn, score it, put the file back.

    `canaries` returns the suite's exit code, so a mutation is CAUGHT when
    the suite goes non-zero. The original text is restored in a `finally`,
    because leaving a mutated policy behind in a served model tree is worse
    than any score this produces.
    """
    caught: dict[str, bool] = {}
    for mutation in mutations:
        target = model_dir / mutation.relative_path
        original = target.read_text(encoding="utf-8")
        try:
            target.write_text(mutation.mutated_text, encoding="utf-8")
            time.sleep(settle)
            caught[mutation.name] = canaries() != 0
        finally:
            target.write_text(original, encoding="utf-8")
            time.sleep(settle)
    return caught


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


def canary_runner(canaries_path: Path) -> Callable[[], int]:
    """Run the canonical matrix runner and hand back its exit code.

    `scripts/cube_rls_matrix.py --expect` already IS the assertion runner,
    including the denial-text regex that makes a quiet zero rows a failure
    against a BLOCKED canary. Re-implementing that here would give the
    mutation score its own, drifting, definition of "red".
    """

    def run_once() -> int:
        return subprocess.run(  # trunk-ignore(bandit/B603): fixed argv, no shell
            [
                sys.executable,
                str(MATRIX_RUNNER),
                "--expect",
                str(canaries_path),
                "--host",
                os.environ[SQL_HOST],
                "--port",
                os.environ.get(SQL_PORT, "15432"),
                "--password",
                os.environ[SQL_PASSWORD],
            ],
            check=False,
            capture_output=True,
            text=True,
        ).returncode

    return run_once


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cube-root", type=Path, default=CUBE_ROOT)
    parser.add_argument("--canaries", type=Path, default=CANARIES_PATH)
    parser.add_argument("--settle", type=float, default=RELOAD_SECONDS)
    args = parser.parse_args(argv)

    missing = [
        name for name in (MODEL_DIR, SQL_HOST, SQL_PASSWORD) if not os.environ.get(name)
    ]
    if missing:
        raise SystemExit(
            "cannot run mutations: set "
            + " and ".join(missing)
            + f". {MODEL_DIR} is the schema directory the Cube under test is "
            "serving — a mutation applied anywhere else is never compiled, and "
            "every mutation then scores uncaught."
        )

    canaries = canary_runner(args.canaries)
    if canaries() != 0:
        raise SystemExit(
            "the canary suite is already failing before any mutation. A "
            "mutation score against a red suite says nothing: every mutation "
            "would read as caught. Fix the suite first."
        )

    results = run(
        policy_mutations(args.cube_root),
        Path(os.environ[MODEL_DIR]),
        canaries,
        settle=args.settle,
    )
    summary = report(results)
    print(summary["verdict"])
    for name in summary["uncaught"]:
        print(f"  UNCAUGHT {name}")
    return exit_code(results)


if __name__ == "__main__":
    raise SystemExit(main())

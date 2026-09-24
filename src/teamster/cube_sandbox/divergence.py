"""Assert that queries a careless kit treats as equivalent are not.

Separate from canaries.yml: a canary going red means the access model broke,
this going red means KTAF's generator regressed. MasterBorn runs the canaries
as their gate and cannot fix this one, and a gate that fails for something the
person holding it cannot fix is how a gate starts getting overridden. One
runner serves both.

Each pair compiles, runs, and returns a plausible wrong number. The fabricated
data has to make each one visibly wrong, or the sandbox teaches that the
careless form is fine.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DIVERGENCES_PATH = Path("src/cube/sandbox/divergences.yml")

# The persona these run as. Every pair reads a student view, so the runner
# needs the one persona with network student scope; a narrower one returns
# zero rows on both sides and both pairs "converge" for the wrong reason.
DEFAULT_VIEWER = "amara.fennworth@ktaf-sandbox.invalid"

# Where the sandbox deployment's SQL API is. Named rather than defaulted to
# localhost: a divergence run against a local dev server proves nothing about
# the sandbox the partner queries.
SQL_HOST = "CUBE_SANDBOX_SQL_HOST"
SQL_PORT = "CUBE_SANDBOX_SQL_PORT"
# trunk-ignore(bandit/B105): the NAME of a variable to read, not a value
SQL_PASSWORD = "CUBE_SANDBOX_SQL_PASSWORD"
SQL_DATABASE = "CUBE_SANDBOX_SQL_DATABASE"
SQL_VIEWER = "CUBE_SANDBOX_SQL_VIEWER"


@dataclass(frozen=True)
class Divergence:
    name: str
    min_ratio: float
    why: str
    a: str
    b: str


def diverges(a: float, b: float, min_ratio: float) -> bool:
    """Whether two results differ by at least min_ratio of the larger.

    Relative to the LARGER of the two, so the ratio means the same thing in
    both directions. Two zeros are equal, not infinitely different, and
    dividing would raise.
    """
    if not a and not b:
        return False
    return abs(a - b) / max(abs(a), abs(b)) >= min_ratio


def load(path: Path = DIVERGENCES_PATH) -> list[Divergence]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out = [Divergence(**entry) for entry in doc.get("divergences", [])]
    if not out:
        raise ValueError(f"{path} declares no divergences")
    for item in out:
        if not 0 < item.min_ratio < 1:
            raise ValueError(
                f"{item.name}: min_ratio must be between 0 and 1, got "
                f"{item.min_ratio}. A ratio of 0 passes on any pair at all."
            )
    return out


def assess(
    divergences: list[Divergence], results: dict[str, tuple[float, float]]
) -> list[dict[str, Any]]:
    """Score each declared divergence against its measured pair."""
    out = []
    for item in divergences:
        pair = results.get(item.name)
        if pair is None:
            out.append({"name": item.name, "status": "unproven", "detail": "not run"})
            continue
        a, b = pair
        held = diverges(a, b, item.min_ratio)
        out.append(
            {
                "name": item.name,
                "status": "held" if held else "converged",
                "detail": f"a={a}, b={b}, min_ratio={item.min_ratio}",
            }
        )
    return out


def exit_code(assessed: list[dict[str, Any]]) -> int:
    # Converged and unproven both fail. A pair that did not run has not shown
    # the lesson any more than one that converged.
    return 1 if any(r["status"] != "held" for r in assessed) else 0


def measure(rows: list[tuple]) -> float:
    """The one number a divergence query yields.

    Two shapes appear in `divergences.yml`. A scalar aggregate returns one
    row of one column, and the number is that value. A grouped query
    (`... GROUP BY DATE_TRUNC(attendance_date, ISOWEEK)`) returns one row per
    bucket, and the number is how many buckets there are — which is exactly
    what the school-week pair compares against the count of school weeks.
    """
    if len(rows) == 1 and len(rows[0]) == 1:
        return float(rows[0][0] or 0)
    return float(len(rows))


def connection_settings() -> dict[str, Any]:
    """Where the sandbox SQL API is, or a message naming what is missing.

    Nothing is defaulted to localhost. A suite that quietly falls back to a
    dev server reports on a deployment nobody ships.
    """
    missing = [name for name in (SQL_HOST, SQL_PASSWORD) if not os.environ.get(name)]
    if missing:
        raise SystemExit(
            "cannot reach the sandbox Cube SQL API: set "
            + " and ".join(missing)
            + ". This suite measures a live deployment and has no offline mode; "
            "run it against the sandbox deployment's production environment, "
            "never a Dev Mode one."
        )
    return {
        "host": os.environ[SQL_HOST],
        "port": int(os.environ.get(SQL_PORT, "15432")),
        "dbname": os.environ.get(SQL_DATABASE, "cube"),
        "user": os.environ.get(SQL_VIEWER, DEFAULT_VIEWER),
        "password": os.environ[SQL_PASSWORD],
    }


def run(divergences: list[Divergence], settings: dict[str, Any]) -> dict[str, tuple]:
    """Measure both sides of every declared pair over one connection.

    Identity is the connecting user on the SQL API, so one connection serves
    every query here: all of them run as the same viewer by design.
    """
    import psycopg

    results: dict[str, tuple[float, float]] = {}
    with psycopg.connect(prepare_threshold=None, **settings) as conn:
        for item in divergences:
            measured = []
            for query in (item.a, item.b):
                with conn.cursor() as cur:
                    # trunk-ignore(pyright/reportCallIssue,pyright/reportArgumentType): declared in divergences.yml, never a literal
                    cur.execute(query)
                    measured.append(measure(cur.fetchall()))
            results[item.name] = (measured[0], measured[1])
    return results


def describe(assessed: list[dict[str, Any]]) -> str:
    return "\n".join(
        f"{result['status'].upper():9s} {result['name']}: {result['detail']}"
        for result in assessed
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--divergences", type=Path, default=DIVERGENCES_PATH)
    args = parser.parse_args(argv)

    divergences = load(args.divergences)
    assessed = assess(divergences, run(divergences, connection_settings()))
    print(describe(assessed))
    return exit_code(assessed)


if __name__ == "__main__":
    raise SystemExit(main())

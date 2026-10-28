"""The builder's view of Cube: every measure with its compiled SQL.

Listing them first keeps the builder from adding a measure Cube already has,
under the same name or another.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .cube_client import _FACT, Cube, CubeError, CubeRefusal, bind
from .decisions import sql_fingerprint
from .pipeline import _measure_expression


@dataclass(frozen=True)
class Member:
    """One measure. `sql` is its compiled expression, `fact` the `fct_*` table
    it reads ("" when none)."""

    name: str
    cube: str
    kind: str
    title: str
    description: str
    sql: str
    sql_fingerprint: str
    fact: str


def members(cube: Cube, skipped: list[dict] | None = None) -> list[Member]:
    """Every measure of every cube and view in `/meta`, each compiled alone.

    Compiling asks Cube for SQL and runs nothing in BigQuery. A measure Cube
    cannot compile or bind is left out and, when `skipped` is given, appended
    to it as `{"name", "reason"}`, so one bad measure does not end the listing.
    """
    found = []

    for entry in cube.meta()["cubes"]:
        for measure in entry.get("measures", []):
            name = measure["name"]
            owner, short = name.split(".", 1)

            try:
                compiled = cube.compiled({"measures": [name]})
                sql = _measure_expression(bind(compiled), owner, short)
            except (CubeError, CubeRefusal) as exc:
                if skipped is not None:
                    skipped.append({"name": name, "reason": str(exc)})
                continue

            facts = _FACT.findall(compiled.sql)
            found.append(
                Member(
                    name=name,
                    cube=entry["name"],
                    kind=entry.get("type", "cube"),
                    title=measure.get("title", ""),
                    description=measure.get("description", ""),
                    sql=sql,
                    sql_fingerprint=sql_fingerprint(sql),
                    fact=facts[0] if facts else "",
                )
            )

    return found


def same_sql(found: list[Member]) -> list[list[Member]]:
    """Groups of measures on different cubes with equal SQL over the same fact.

    The expression alone is not enough: `count(distinct t.student_id)` on 2
    facts counts different students. Views are left out: a view member repeats
    its cube's.
    """
    by_sql = defaultdict(list)

    for m in found:
        if m.kind != "view":
            by_sql[(m.fact, m.sql_fingerprint)].append(m)

    return [group for group in by_sql.values() if len({m.cube for m in group}) > 1]


def same_name(found: list[Member], name: str) -> list[Member]:
    """Every member named `name` (the part after the cube) on any cube."""
    return [m for m in found if m.name.split(".", 1)[1] == name]

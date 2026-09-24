"""Assert no reserved surname belongs to a real KTAF person.

The reserved list is a tripwire in two directions. A surname OUTSIDE it means
a row got in from somewhere it should not have. A surname INSIDE it means the
row is fabricated. The second direction is the one that decays: it holds only
while no real staff member or student carries any of these names, and that is
a fact about production, not about the file.

So it is checked, not asserted in a comment. A name is rejected on a count of
one — Brunson was, at 10, after being asked for by name — because "rare" and
"absent" are different claims and only the second is the one the docs make.

This reads production, which the generator never does. It runs on demand
rather than in CI, where there are no warehouse credentials:

    uv run python -m teamster.cube_sandbox.collisions

Exit 0 when every surname is absent, 1 when any is not.
"""

from __future__ import annotations

import argparse
from typing import Any

PRODUCTION_PROJECT = "teamster-332318"
STAFF_TABLE = f"{PRODUCTION_PROJECT}.kipptaf_marts.dim_staff"
STUDENT_TABLE = f"{PRODUCTION_PROJECT}.kipptaf_marts.dim_students"

# No regex. A surname is caller data from a YAML file, and BigQuery has no
# REGEXP_ESCAPE, so `Diggins-Smith` or any future name carrying a
# metacharacter would change what the pattern means. Padding both sides with
# a space gives a whole-token match that needs no escaping and handles a
# two-word surname like `Delle Donne` as one token.
# trunk-ignore(bandit/B608): the two interpolated names are module constants; the candidate surnames are bound as @names
COLLISION_SQL = f"""
WITH candidates AS (SELECT name FROM UNNEST(@names) AS name)
SELECT
  c.name AS name,
  (
    SELECT COUNT(*) FROM `{STAFF_TABLE}` s
    WHERE LOWER(s.last_name) = LOWER(c.name)
  ) AS staff_hits,
  (
    SELECT COUNTIF(
      STRPOS(CONCAT(' ', LOWER(st.full_name), ' '), CONCAT(' ', LOWER(c.name), ' ')) > 0
    ) FROM `{STUDENT_TABLE}` st
  ) AS student_hits
FROM candidates c
ORDER BY staff_hits + student_hits DESC, name
"""


def collisions(rows: list[Any]) -> list[tuple[str, int, int]]:
    """Every candidate a real person shares, worst first."""
    return [
        (row.name, row.staff_hits, row.student_hits)
        for row in rows
        if row.staff_hits or row.student_hits
    ]


def describe(found: list[tuple[str, int, int]], checked: int) -> str:
    if not found:
        return (
            f"{checked} reserved surnames checked against production: "
            "no KTAF staff member or student carries any of them"
        )
    lines = [f"{len(found)} of {checked} reserved surnames belong to real KTAF people:"]
    lines.extend(
        f"  {name}: {staff} staff, {students} students"
        for name, staff, students in found
    )
    lines.append(
        "Remove them. A surname from the reserved list is supposed to prove a "
        "row is fabricated, and for these it proves nothing."
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    from google.cloud import bigquery

    from teamster.cube_sandbox import generate

    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)

    surnames = generate.reserved_surnames()
    client = bigquery.Client(project=PRODUCTION_PROJECT)
    rows = list(
        client.query(
            COLLISION_SQL,
            job_config=bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ArrayQueryParameter("names", "STRING", surnames)
                ]
            ),
        ).result()
    )
    found = collisions(rows)
    print(describe(found, len(surnames)))
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())

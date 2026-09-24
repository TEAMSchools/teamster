"""Assert the generated rows satisfy the coverage contract.

Saturating every column and every join path is what leaves no empty niche for
a sloppy kit assumption to occupy. The manifest defines what saturated means;
this asserts it — one observed count per cell, non-zero exit on any zero.
"""

from __future__ import annotations

from typing import Any

# Cells that name no table are not row-countable. They are real requirements
# (hasRemit/hasChain both ways, the unresolvable identity, the three
# divergences), but proving them needs a live query against the deployment,
# not a scan of generated rows. Scoring them zero and calling them uncovered
# would blame the generator for something it was never asked to produce, so
# they are reported "unproven" and still fail the run.
_UNCOUNTABLE = {"derived", "identity", "divergence"}
_COUNTABLE = {"null", "non_null", "scope", "orphan"}


def assess(manifest: dict[str, Any], tables: dict[str, list[dict]]) -> list[dict]:
    out = []
    for cell in manifest["cells"]:
        kind = cell["kind"]
        if kind in _UNCOUNTABLE:
            out.append({**cell, "observed": 0, "status": "unproven"})
            continue
        if kind not in _COUNTABLE:
            raise ValueError(f"unknown cell kind {kind!r} on {cell}")

        rows = tables.get(cell["table"], []) if cell["table"] else []
        column = cell["column"]
        if kind == "null":
            # `column in row` matters: a column the generator never wrote is
            # absent, not null, and counting it as a null row would let a
            # generator satisfy the null contract by omitting the column.
            observed = sum(1 for r in rows if column in r and r[column] is None)
        elif kind == "non_null":
            observed = sum(1 for r in rows if r.get(column) is not None)
        elif kind == "orphan":
            # `detail` names the counterpart column across the join path.
            # The test is symmetric: a child row whose key matches no parent,
            # or a parent row no child references, is "my non-null value is
            # absent from their value set" either way. Nulls are excluded —
            # a missing reference is not an unmatched one.
            other_table, _, other_column = cell["detail"].partition(".")
            theirs = {
                r[other_column]
                for r in tables.get(other_table, [])
                if r.get(other_column) is not None
            }
            observed = sum(
                1 for r in rows if r.get(column) is not None and r[column] not in theirs
            )
        else:
            observed = sum(1 for r in rows if str(r.get(column)) == cell["detail"])

        out.append(
            {
                **cell,
                "observed": observed,
                "status": "covered" if observed else "uncovered",
            }
        )
    return out


def uncovered(assessed: list[dict]) -> list[tuple[str, str | None, str | None, str]]:
    """Every cell the run did not satisfy, for the operator to read."""
    return [
        (c["kind"], c["table"], c["column"], c["detail"])
        for c in assessed
        if c["observed"] == 0
    ]


def exit_code(assessed: list[dict]) -> int:
    return 1 if any(c["observed"] == 0 for c in assessed) else 0

"""Assert the generated rows satisfy the coverage contract.

Saturating every column and every join path is what leaves no empty niche for
a sloppy kit assumption to occupy. The manifest defines what saturated means;
this asserts it — one observed count per cell, non-zero exit on any cell the
generated rows fail to satisfy.
"""

from __future__ import annotations

from typing import Any

# Cells that name no table are not row-countable. They are real requirements
# (hasRemit/hasChain both ways, the unresolvable identity, the three
# divergences), but proving them needs a live query against the deployment,
# not a scan of generated rows. Scoring them zero and calling them uncovered
# would blame the generator for something it was never asked to produce, so
# they are reported "unproven" and DO NOT fail the run.
#
# Failing on them made the gate unreachable: the manifest holds eight such
# cells permanently, so a perfect dataset still exited 1 and the exit code
# carried no information at all. What proves them is the canary suite and the
# divergence suite, each of which has its own non-zero exit. This one asserts
# what the generated rows can show, and reports the rest as unproven so the
# operator can see they were never assessed here.
_UNCOUNTABLE = {"derived", "identity", "divergence"}
_COUNTABLE = {"null", "non_null", "scope", "scope_variety", "orphan"}

# `scope_variety` needs TWO distinct non-none values, not one. access.js
# branches on `!== "none"` for the sensitive tiers, so a single non-none value
# lets a kit author write an equality check that passes every test — exactly
# the mistake the sandbox exists to expose.
_MIN_DISTINCT_NON_NONE = 2


def assess(manifest: dict[str, Any], tables: dict[str, list[dict]]) -> list[dict]:
    out = []
    for cell in manifest["cells"]:
        kind = cell["kind"]
        if kind in _UNCOUNTABLE:
            out.append({**cell, "observed": 0, "status": "unproven"})
            continue
        if kind not in _COUNTABLE:
            raise ValueError(f"unknown cell kind {kind!r} on {cell}")
        required = _MIN_DISTINCT_NON_NONE if kind == "scope_variety" else 1

        rows = tables.get(cell["table"], []) if cell["table"] else []
        column = cell["column"]
        if kind == "null":
            # `column in row` matters: a column the generator never wrote is
            # absent, not null, and counting it as a null row would let a
            # generator satisfy the null contract by omitting the column.
            observed = sum(1 for r in rows if column in r and r[column] is None)
        elif kind == "non_null":
            observed = sum(1 for r in rows if r.get(column) is not None)
        elif kind == "scope_variety":
            # Distinct values, not rows: a thousand rows carrying one value
            # still leave the equality check unbroken.
            observed = len(
                {
                    r[column]
                    for r in rows
                    if r.get(column) is not None and r[column] != "none"
                }
            )
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
                "status": "covered" if observed >= required else "uncovered",
            }
        )
    return out


def _named(
    assessed: list[dict], status: str
) -> list[tuple[str, str | None, str | None, str]]:
    return [
        (c["kind"], c["table"], c["column"], c["detail"])
        for c in assessed
        if c["status"] == status
    ]


def uncovered(assessed: list[dict]) -> list[tuple[str, str | None, str | None, str]]:
    """Every countable cell the run did not satisfy. These fail the run."""
    return _named(assessed, "uncovered")


def unproven(assessed: list[dict]) -> list[tuple[str, str | None, str | None, str]]:
    """Cells row counting cannot evaluate, reported rather than failed.

    Listed separately and loudly: an operator reading "0 uncovered" must
    still see that eight requirements were never assessed here, and which
    suite does assess them.
    """
    return _named(assessed, "unproven")


def describe(assessed: list[dict]) -> str:
    """One line per outcome, so a green run still names what it did not prove."""
    lines = [
        f"{sum(1 for c in assessed if c['status'] == 'covered')} covered, "
        f"{len(uncovered(assessed))} uncovered, "
        f"{len(unproven(assessed))} unproven"
    ]
    lines += [
        f"  uncovered: {kind} {table}.{column} — {detail}"
        for kind, table, column, detail in uncovered(assessed)
    ]
    if unproven(assessed):
        lines.append(
            "  unproven cells are asserted by the canary and divergence "
            "suites, not by counting rows:"
        )
        lines += [
            f"    {kind} {column or ''} {detail}".rstrip()
            for kind, _, column, detail in unproven(assessed)
        ]
    return "\n".join(lines)


def exit_code(assessed: list[dict]) -> int:
    """Non-zero on an UNCOVERED cell only.

    An unproven cell is not a generator failure, and failing on one made this
    gate impossible to pass — see the note on _UNCOUNTABLE above.
    """
    return 1 if any(c["status"] == "uncovered" for c in assessed) else 0

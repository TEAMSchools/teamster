"""Assert the generated rows satisfy the coverage contract.

Saturating every column and every join path is what leaves no empty niche for
a sloppy kit assumption to occupy. The manifest defines what saturated means;
this asserts it — one observed count per cell, non-zero exit on any cell the
generated rows fail to satisfy.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

import yaml

MANIFEST_PATH = Path("src/cube/sandbox/coverage_manifest.yml")
DEFAULT_AVRO_DIR = Path("build/cube_sandbox/tiny")

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


def read_avro(avro_dir: Path, tables: set[str]) -> dict[str, list[dict]]:
    """Read the generated Avro back, one file per table.

    Reading the written files rather than the in-memory rows is the point: a
    value that does not survive the Avro round trip — a null that became an
    empty string, a NUMERIC that lost its scale — is a value the sandbox will
    not have, and an assessment against the in-memory dict would never see
    it.
    """
    import fastavro

    out: dict[str, list[dict]] = {}
    missing = []
    for table in sorted(tables):
        path = avro_dir / f"{table}.avro"
        if not path.exists():
            missing.append(path)
            continue
        with path.open("rb") as handle:
            # fastavro types its reader as yielding AvroMessage, a union wide
            # enough to include a bare scalar. Every record here is a record
            # type, because avro_schema only ever emits one.
            records = cast("Iterable[dict[str, Any]]", fastavro.reader(handle))
            out[table] = list(records)
    if missing:
        raise SystemExit(
            "no Avro to assess — run "
            "`uv run python -m teamster.cube_sandbox.generate` first. Missing: "
            + ", ".join(str(path) for path in missing)
        )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--avro-dir", type=Path, default=DEFAULT_AVRO_DIR)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    args = parser.parse_args(argv)

    manifest = yaml.safe_load(args.manifest.read_text(encoding="utf-8")) or {}
    if not manifest.get("cells"):
        raise SystemExit(f"{args.manifest} declares no cells")
    wanted = {cell["table"] for cell in manifest["cells"] if cell["table"]}
    assessed = assess(manifest, read_avro(args.avro_dir, wanted))
    print(describe(assessed))
    return exit_code(assessed)


if __name__ == "__main__":
    raise SystemExit(main())

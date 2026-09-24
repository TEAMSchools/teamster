"""Generate the coverage contract.

Hand-writing this list would let it go stale silently. Generating it turns a
new column, view or scope value into an uncovered cell instead of an absence
nobody notices.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from teamster.cube_sandbox import model, personas, snapshot
from teamster.cube_sandbox.personas import Persona

CUBE_ROOT = Path("src/cube")
MARTS_ROOT = Path("src/dbt/kipptaf/models/marts")
PERSONAS_PATH = CUBE_ROOT / "sandbox" / "personas.yml"
MANIFEST_PATH = CUBE_ROOT / "sandbox" / "coverage_manifest.yml"


def _is_not_null_test(test: Any) -> bool:
    """True only for a bare `not_null` test, never `not_null_proportion` et al.

    `not_null_proportion` asserts a PROPORTION of non-null rows, not the
    absence of nulls. A substring match on "not_null" would also match it (and
    any other test whose name merely contains "not_null"), wrongly exempting a
    column that genuinely does contain nulls from ever getting a required null
    cell. A test is the real not-null contract only when it is the bare string
    `"not_null"`, or a one-key mapping whose only key is `"not_null"` (the
    shape a `config:` block on the test takes).
    """
    if test == "not_null":
        return True
    return isinstance(test, dict) and set(test) == {"not_null"}


def dbt_not_null(marts_root: Path) -> set[tuple[str, str]]:
    """Columns dbt asserts are never null, as (table, column).

    INFORMATION_SCHEMA reports every kipptaf_marts column NULLABLE, so it
    exempts nothing. These tests carry the real contract, and they are
    committed, so reading them needs no production access. Reads both the
    current `data_tests:` key and the legacy `tests:` key.
    """
    out: set[tuple[str, str]] = set()
    for path in marts_root.rglob("*.yml"):
        doc = yaml.safe_load(path.read_text()) or {}
        for m in doc.get("models", []):
            for col in m.get("columns", []):
                tests = col.get("data_tests", col.get("tests", []))
                if any(_is_not_null_test(t) for t in tests):
                    out.add((m["name"], col["name"]))
    return out


def build(
    *,
    snap: dict[str, Any],
    referenced: dict[str, set[str]],
    key_columns: set[tuple[str, str]],
    policy_columns: set[tuple[str, str]],
    not_null: set[tuple[str, str]],
    scopes: dict[str, set[str]],
    people: list[Persona],
    join_paths: list[model.JoinPath],
) -> dict[str, Any]:
    """Every cell the sandbox data must contain.

    Keyword-only: all five set-shaped parameters are interchangeable
    positionally, and a positional call that silently binds key_columns to
    policy_columns would produce a plausible manifest with the wrong
    exemptions.
    """
    cells: list[dict[str, Any]] = []

    for table, columns in sorted(snap["tables"].items()):
        for column in sorted(columns):
            if column not in referenced.get(table, set()):
                continue
            cells.append(
                {
                    "kind": "non_null",
                    "table": table,
                    "column": column,
                    "detail": "at least one non-null row",
                    "status": "uncovered",
                }
            )
            # Three derived exemptions, never a name heuristic: a join or
            # surrogate key (a null one breaks the fixtures), a column an
            # access_policy filters on (a null one makes the persona resolve
            # to nothing), and a column dbt asserts is never null.
            exempt = (
                (table, column) in key_columns
                or (table, column) in policy_columns
                or (table, column) in not_null
            )
            if not exempt:
                cells.append(
                    {
                        "kind": "null",
                        "table": table,
                        "column": column,
                        "detail": "at least one null row",
                        "status": "uncovered",
                    }
                )

    # staff_pii_scope maps to its four real values. The three sensitive tiers
    # (staff_compensation_scope, staff_observations_scope,
    # staff_benefits_scope) map to the sentinel "__non_none__" because
    # access.js branches on `!== "none"` rather than a value list for them —
    # any non-none value is valid, and no single value stands in for the
    # domain, so no scope cell is emitted for them below.
    declared = {
        (name, value)
        for p in people
        for name, value in p.scopes.items()
        if value != "none"
    }

    for name, values in sorted(scopes.items()):
        for value in sorted(values):
            if value == "__non_none__":
                continue
            cells.append(
                {
                    "kind": "scope",
                    "table": "dim_staff_cube_access",
                    "column": name,
                    "detail": value,
                    "status": "uncovered",
                }
            )

    undeclared = {
        (n, v)
        for n, v in declared
        if v not in scopes.get(n, set()) and "__non_none__" not in scopes.get(n, set())
    }
    if undeclared:
        raise ValueError(
            "personas.yml declares scope values access.js does not handle: "
            f"{sorted(undeclared)}"
        )

    for state in ("hasRemit", "hasChain"):
        for value in ("true", "false"):
            cells.append(
                {
                    "kind": "derived",
                    "table": None,
                    "column": state,
                    "detail": value,
                    "status": "uncovered",
                }
            )

    # One orphan on each side of every join path. Symmetric on purpose: a
    # child row whose foreign key matches no parent, and a parent row no
    # child references. `detail` names the counterpart, which is what lets
    # coverage evaluate the cell and what makes the path a named fixture.
    for path in join_paths:
        for (table, column), (other_table, other_column) in (
            (path.child, path.parent),
            (path.parent, path.child),
        ):
            cells.append(
                {
                    "kind": "orphan",
                    "table": table,
                    "column": column,
                    "detail": f"{other_table}.{other_column}",
                    "status": "uncovered",
                }
            )

    cells.append(
        {
            "kind": "identity",
            "table": None,
            "column": None,
            "detail": "one email with no dim_staff_cube_access row",
            "status": "uncovered",
        }
    )

    for name in (
        "unpinned_cumulative",
        "attendance_view_weighting",
        "school_week_vs_iso",
    ):
        cells.append(
            {
                "kind": "divergence",
                "table": None,
                "column": None,
                "detail": name,
                "status": "uncovered",
            }
        )

    return {"cells": cells}


class _PrettierDumper(yaml.SafeDumper):
    """Match the repo's prettier-formatted YAML so the committed diff is
    already lint-clean: indented block sequences, and the YAML-ambiguous
    scalars ("null", "true", "false") double-quoted rather than left as bare
    keywords or single-quoted."""

    def increase_indent(self, flow: bool = False, indentless: bool = False):
        return super().increase_indent(flow=flow, indentless=False)


def _str_representer(dumper: _PrettierDumper, data: str) -> yaml.Node:
    style = '"' if data in {"null", "true", "false"} else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


_PrettierDumper.add_representer(str, _str_representer)


def _dump(data: dict[str, Any]) -> str:
    return yaml.dump(
        data, Dumper=_PrettierDumper, sort_keys=False, default_flow_style=False
    )


def main() -> int:
    result = build(
        snap=snapshot.load(),
        referenced=model.referenced_columns(CUBE_ROOT),
        key_columns=model.key_columns(CUBE_ROOT),
        policy_columns=model.policy_columns(CUBE_ROOT),
        not_null=dbt_not_null(MARTS_ROOT),
        scopes=model.scope_values(CUBE_ROOT / "access.js"),
        people=personas.load(PERSONAS_PATH),
        join_paths=model.join_paths(CUBE_ROOT),
    )

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(_dump(result))
    print(f"wrote {MANIFEST_PATH}: {len(result['cells'])} cells")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

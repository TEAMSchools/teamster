# /// script
# requires-python = ">=3.13"
# dependencies = ["google-cloud-bigquery", "pyyaml"]
# ///
"""Generate the Cube sandbox coverage manifest from production introspection.

Writes ``src/cube/sandbox/coverage_manifest.yml``: one entry per cell the
synthetic dataset must contain. That file is three things at once -- the data
generator's specification, the CI assertion target, and half the drift detector
-- which is why it is generated rather than hand-written. A hand-written list
goes stale silently; a generated one turns a new column, view, or scope enum
into an ``uncovered`` cell.

See ``docs/superpowers/specs/2026-09-11-cube-sandbox-build-design.md``, Piece 2.

WHAT IT READS

- Production ``INFORMATION_SCHEMA.COLUMNS`` for the 20 mart tables -> column
  cells, and the codesets of the categorical fields. Schema and distinct
  values only. **No rows.**
- ``src/cube/model/**/*.yml`` -> the ``sql_table:`` set and the views' groups.
- ``src/cube/cube.js`` -> the tables identity resolution reads directly.
- ``src/cube/access.js`` -> the scope enum domain the CODE handles.
- ``src/cube/sandbox/reserved_names.yml`` -> the name character classes.

TWO TRAPS IT EXISTS TO AVOID

``dim_staff_reporting_chain`` appears in no cube YAML -- only ``cube.js`` reads
it. Deriving the table set from ``sql_table:`` alone finds 19 and misses it,
and the failure is quiet: every view still compiles, and only the
``reporting_chain`` personas break. So the table set is the union of both
sources and the count is asserted.

Production data is a SUBSET of the enum domain ``access.js`` handles. Three
``staff_pii_scope`` values and every non-``none`` ``staff_benefits_scope`` have
zero production rows, so a manifest built from ``SELECT DISTINCT`` would omit
live policy branches. Scope cells come from the code; codesets come from the
data. Those are different questions and they have different sources.

USAGE

    uv run scripts/sandbox_coverage_manifest.py

Needs BigQuery access for the introspection half. To run the build without
credentials -- in a test, or to review the logic -- pass a pre-fetched payload:

    uv run scripts/sandbox_coverage_manifest.py --introspection payload.json

``--dump-introspection`` writes that payload, so a fetch can be captured once
and replayed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CUBE_ROOT = REPO_ROOT / "src" / "cube"
MODEL_ROOT = CUBE_ROOT / "model"
DEFAULT_OUT = CUBE_ROOT / "sandbox" / "coverage_manifest.yml"
RESERVED_NAMES = CUBE_ROOT / "sandbox" / "reserved_names.yml"

PROD_PROJECT = "teamster-332318"
MARTS_DATASET = "kipptaf_marts"

# The 6 views the sandbox must resolve. Asserted, so a view added to the model
# without being added here fails loudly rather than going uncovered.
EXPECTED_VIEWS = {
    "staff_directory",
    "staff_pii",
    "student_assessment_scores_view",
    "student_attendance_view",
    "student_enrollments_view",
    "student_section_enrollments_view",
}

# 19 tables reachable from `sql_table:`, plus dim_staff_reporting_chain, which
# only cube.js reads. See "TWO TRAPS" above.
EXPECTED_TABLE_COUNT = 20

# queryRewrite injects one of these depending on query granularity. Each must
# be non-uniform in the sandbox -- strictly between 0 and 1 -- or anchored
# measures silently look additive and the partner never learns the rule.
SNAPSHOT_ANCHORS = [
    "is_latest_record",
    "is_month_end_record",
    "is_week_end_record",
    "is_current_record",
]

# Columns whose distinct values a consumer will put in a dropdown, a filter, or
# a group-by, so the sandbox has to carry the whole domain. Declared rather than
# inferred: "low cardinality" would also catch columns nobody facets on, and
# would silently change as production data shifts.
CODESET_COLUMNS = [
    # The 7 scope columns. Needed because a scope cell marked `any_non_none`
    # tells a generator to pick a real value but not which values exist.
    ("dim_staff_cube_access", "student_location_scope"),
    ("dim_staff_cube_access", "staff_location_scope"),
    ("dim_staff_cube_access", "staff_department_scope"),
    ("dim_staff_cube_access", "staff_pii_scope"),
    ("dim_staff_cube_access", "staff_compensation_scope"),
    ("dim_staff_cube_access", "staff_observations_scope"),
    ("dim_staff_cube_access", "staff_benefits_scope"),
    ("dim_students", "gender_identity"),
    ("dim_students", "race"),
    ("dim_students", "enrollment_status"),
    ("dim_staff", "gender_identity"),
    ("dim_staff", "race"),
]


# --- Repo-side parsing (no credentials, no network) -------------------------


def cube_model_tables() -> set[str]:
    """Every `kipptaf_marts.<table>` named by a `sql_table:` in the model."""
    pattern = re.compile(rf"sql_table:\s*{MARTS_DATASET}\.(\w+)")
    tables: set[str] = set()
    for path in MODEL_ROOT.rglob("*.yml"):
        tables.update(pattern.findall(path.read_text(encoding="utf-8")))
    return tables


def identity_resolution_tables() -> set[str]:
    """Tables cube.js reads directly, which no `sql_table:` mentions."""
    source = (CUBE_ROOT / "cube.js").read_text(encoding="utf-8")
    return set(re.findall(rf"{MARTS_DATASET}\.(\w+)", source))


def view_groups() -> dict[str, list[str]]:
    """Map each view to the securityContext groups its access_policy gates on."""
    groups: dict[str, list[str]] = {}
    for path in (MODEL_ROOT / "views").rglob("*.yml"):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for view in doc.get("views", []):
            found = [
                policy["group"]
                for policy in view.get("access_policy", [])
                if isinstance(policy, dict) and policy.get("group")
            ]
            groups[view["name"]] = sorted(set(found))
    return groups


def scope_domain() -> dict[str, dict[str, Any]]:
    """The scope values access.js handles -- the CODE's domain, not the data's.

    Parses three known structures rather than evaluating JS. Each result is
    asserted below, so an access.js refactor breaks this loudly instead of
    quietly emitting fewer cells than the policies need.
    """
    source = (CUBE_ROOT / "access.js").read_text(encoding="utf-8")

    def cases(after: str) -> list[str]:
        # `case "x":` literals inside the function starting at `after`.
        body = source[source.index(after) :]
        end = body.find("\n}\n")
        return re.findall(r'case\s+"(\w+)":', body[: end if end > 0 else len(body)])

    # Scopes the code branches on by VALUE: each literal needs its own cell.
    enumerated = {
        "staff_pii_scope": cases("function buildGroups"),
        "staff_location_scope": cases("function computeAllowedAbbreviations"),
        "staff_department_scope": cases("function computeAllowedDepartmentGroups"),
    }
    # student_location_scope is not a switch -- buildGroups emits
    # `student-<scope>` for any non-none value, and the 3 real tiers are what
    # computeAllowedAbbreviations resolves.
    enumerated["student_location_scope"] = enumerated["staff_location_scope"]

    domain = {
        column: {"kind": "literal", "values": sorted(set(values) | {"none"})}
        for column, values in enumerated.items()
        if values
    }

    # The forward-compat tiers in STAFF_SENSITIVE_TIERS. buildGroups emits the
    # group for ANY non-none value, so the code distinguishes exactly 2 states
    # and there is no third literal to cover. But "non-none" is not itself a
    # storable value -- a generator must write a real one -- so the cell says
    # so and points at the codeset for the concrete choice.
    for scope in re.findall(r'scope:\s*"(\w+)"', source):
        domain.setdefault(
            scope,
            {
                "kind": "any_non_none",
                "values": ["none"],
                "concrete_values_from": f"dim_staff_cube_access.{scope}",
            },
        )
    return domain


def name_classes() -> list[str]:
    """Character classes the reserved-name fixture says a dataset must cover."""
    doc = yaml.safe_load(RESERVED_NAMES.read_text(encoding="utf-8"))
    return sorted({entry["class"] for entry in doc["given_names"]})


# --- Production introspection (credentials) ---------------------------------


def fetch_introspection(tables: list[str]) -> dict[str, Any]:
    """Read schema and codesets from production. Schema and distinct values only."""
    from google.cloud import bigquery

    client = bigquery.Client(project=PROD_PROJECT)
    names = ", ".join(f"'{t}'" for t in tables)
    columns = [
        dict(row)
        for row in client.query(
            # trunk-ignore(bandit/B608): identifiers are repo constants; table names are parsed from the cube model, never user input
            f"""
            SELECT table_name, column_name, data_type, is_nullable
            FROM `{PROD_PROJECT}.{MARTS_DATASET}.INFORMATION_SCHEMA.COLUMNS`
            WHERE table_name IN ({names})
            ORDER BY table_name, ordinal_position
            """
        ).result()
    ]

    codesets: dict[str, list[str]] = {}
    for table, column in CODESET_COLUMNS:
        rows = client.query(
            # trunk-ignore(bandit/B608): table and column come from CODESET_COLUMNS, a literal in this file
            f"SELECT DISTINCT {column} AS v "
            f"FROM `{PROD_PROJECT}.{MARTS_DATASET}.{table}`"
        ).result()
        # None is kept as a distinct member: a nullable categorical whose
        # generator never emits null is a missing cell, not a tidy dataset.
        codesets[f"{table}.{column}"] = sorted(
            (r["v"] for r in rows), key=lambda v: (v is not None, v or "")
        )
    return {"columns": columns, "codesets": codesets}


# --- Manifest assembly ------------------------------------------------------


def build_manifest(introspection: dict[str, Any], tables: list[str]) -> dict[str, Any]:
    """Assemble every required cell, each marked uncovered."""
    columns = introspection["columns"]

    column_cells = [
        {
            "table": col["table_name"],
            "column": col["column_name"],
            "data_type": col["data_type"],
            # Every mart column behind these views is nullable, so the
            # not-nullable exemption never fires in practice -- but derive it
            # rather than assume it, so a future NOT NULL is handled.
            "residents": (
                ["null", "non_null"] if col["is_nullable"] == "YES" else ["non_null"]
            ),
            "status": "uncovered",
        }
        for col in columns
    ]

    codesets = introspection["codesets"]

    def gap(spec: dict[str, Any], value: str) -> dict[str, str]:
        """Flag an any_non_none cell production cannot supply a value for.

        access.js handles a non-none value for every tier, but production data
        need not contain one -- staff_benefits_scope is `none` for every row
        today. The cell is still required, so the generator has to invent a
        value. Saying so here makes that a decision rather than a surprise.
        """
        source = spec.get("concrete_values_from")
        if value == "none" or not source:
            return {}
        available = [v for v in codesets.get(source, []) if v not in (None, "none")]
        if available:
            return {"concrete_values_from": source}
        return {
            "concrete_values_from": source,
            "gap": "No non-none value exists in production. The generator must "
            "invent one, and no production row will ever exercise this branch.",
        }

    scope_cells = [
        {
            "column": column,
            "value": value,
            "kind": spec["kind"],
            "source": "access.js",
            "status": "uncovered",
            **gap(spec, value),
        }
        for column, spec in sorted(scope_domain().items())
        # An any_non_none scope needs 2 cells: the none branch, and one
        # standing for every other value. "non_none" is a marker, never a
        # value to write -- concrete_values_from says where the real one is.
        for value in (
            spec["values"] if spec["kind"] == "literal" else ["none", "non_none"]
        )
    ]

    return {
        "generated_by": "scripts/sandbox_coverage_manifest.py",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%d"),
        "source": {
            "project": PROD_PROJECT,
            "dataset": MARTS_DATASET,
            "tables": len(tables),
            "note": "Schema and codesets only. No rows are read from production.",
        },
        "totals": {
            "column_cells": len(column_cells),
            "residents": sum(len(c["residents"]) for c in column_cells),
            "scope_cells": len(scope_cells),
        },
        "tables": sorted(tables),
        "views": view_groups(),
        "columns": column_cells,
        "scopes": scope_cells,
        # buildGroups branches on these, and an empty remit or chain takes the
        # no-group default-deny path rather than emitting a group. Unreachable
        # in production by design, so only the sandbox can exercise it.
        "derived_states": [
            {"name": name, "value": value, "status": "uncovered"}
            for name in ("hasRemit", "hasChain")
            for value in (True, False)
        ],
        "anchors": [
            {"column": anchor, "requirement": "mixed", "status": "uncovered"}
            for anchor in SNAPSHOT_ANCHORS
        ],
        "name_classes": [
            {"class": cls, "status": "uncovered"} for cls in name_classes()
        ],
        "codesets": introspection["codesets"],
        "identities": [
            {
                "name": "unresolvable",
                "note": "No dim_staff_cube_access row at all, to exercise "
                "clean default-deny.",
                "status": "uncovered",
            }
        ],
    }


def _display(path: Path) -> str:
    """Repo-relative when it can be, absolute otherwise.

    `Path.relative_to` raises for a path outside the repo, and `--out` accepts
    any path, so formatting the summary line would crash AFTER the file was
    already written.
    """
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--introspection", type=Path, help="Replay a saved payload instead of querying."
    )
    parser.add_argument("--dump-introspection", type=Path)
    args = parser.parse_args()

    tables = cube_model_tables() | identity_resolution_tables()
    if len(tables) != EXPECTED_TABLE_COUNT:
        model_only = sorted(cube_model_tables())
        print(
            f"Expected {EXPECTED_TABLE_COUNT} tables, found {len(tables)}. "
            f"{len(model_only)} come from sql_table:, the rest from cube.js. "
            "A table reachable from neither is invisible to the sandbox, and "
            "the failure is quiet -- views still compile. Nothing written.\n"
            f"Found: {sorted(tables)}",
            file=sys.stderr,
        )
        return 1

    views = view_groups()
    missing_views = EXPECTED_VIEWS - views.keys()
    if missing_views:
        print(f"Views missing from the model: {sorted(missing_views)}", file=sys.stderr)
        return 1
    ungated = [name for name in EXPECTED_VIEWS if not views[name]]
    if ungated:
        print(
            f"Views with no access_policy group: {sorted(ungated)}. Every view "
            "is gated, so this means the parse broke, not that a view is open.",
            file=sys.stderr,
        )
        return 1

    domain = scope_domain()
    if len(domain.get("staff_pii_scope", {}).get("values", [])) < 4:
        print(
            "Parsed fewer than 4 staff_pii_scope values from access.js. "
            "staff_pii.yml carries a policy for each, so a short parse would "
            "silently drop policy branches. Nothing written.",
            file=sys.stderr,
        )
        return 1

    if args.introspection:
        introspection = json.loads(args.introspection.read_text(encoding="utf-8"))
    else:
        introspection = fetch_introspection(sorted(tables))

    if args.dump_introspection:
        args.dump_introspection.write_text(
            json.dumps(introspection, indent=2, default=str), encoding="utf-8"
        )

    if not introspection["columns"]:
        print("No columns returned. Nothing written.", file=sys.stderr)
        return 1

    # A payload that predates a new CODESET_COLUMNS entry would leave that
    # codeset absent, and `gap()` cannot tell "production has no non-none
    # value" from "we never asked" -- it would report a phantom gap and write a
    # manifest that differs from a live run with no warning. Refuse instead.
    expected = {f"{table}.{column}" for table, column in CODESET_COLUMNS}
    missing = sorted(expected - introspection["codesets"].keys())
    if missing:
        print(
            f"Introspection payload is missing {len(missing)} codeset(s): "
            f"{missing}. It predates a CODESET_COLUMNS change. Re-fetch rather "
            "than replaying, or the gap report is wrong. Nothing written.",
            file=sys.stderr,
        )
        return 1

    manifest = build_manifest(introspection, sorted(tables))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True, width=88),
        encoding="utf-8",
    )

    totals = manifest["totals"]
    print(
        f"Wrote {_display(args.out)}: "
        f"{len(tables)} tables, {totals['column_cells']} columns "
        f"({totals['residents']} residents), {totals['scope_cells']} scope cells, "
        f"{len(manifest['name_classes'])} name classes"
    )
    for cell in (c for c in manifest["scopes"] if "gap" in c):
        print(
            f"  gap: {cell['column']} has no non-none value in production. "
            "Required by access.js, so the generator must invent one.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

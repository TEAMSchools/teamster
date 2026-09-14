"""Generate a TypeScript declaration file from the committed Cube catalog.

Reads ``docs/reference/cube-catalog-meta.json`` and writes
``docs/reference/cube-catalog.d.ts``: one member-name union and one row
interface per view, plus a view-keyed ``CubeQuery`` generic.

Offline by design. The catalog snapshot is committed, so this needs no Cube
credentials and no network -- anyone who can clone the repo can regenerate the
types. Run ``cube_catalog_export.py`` first when the model has moved; this
script only reshapes what that one already fetched.

Why it exists: a partner building against the semantic layer gets the shape as
something their compiler checks, not something they read. Two properties earn
it over the raw JSON:

- Every member description becomes JSDoc, so the model's own warnings -- the
  scope-bound measure traps in particular -- surface on hover at the moment a
  developer picks a measure, rather than in a document they read once.
- Measure values are typed ``string``. Cube returns numeric measures as JSON
  strings (``"900"``, not ``900``), so a consumer that assumes ``number``
  breaks at runtime on arithmetic. Typing it honestly turns that into a
  compile error.

Usage::

    uv run scripts/cube_types_export.py

Commit the output. A model change then surfaces as a reviewable diff in both
the catalog and the types.

Like ``generate_marts_reference.py``, commit the output in its prettier-
formatted form. This script is NOT idempotent against the committed file:
prettier collapses short unions that this emits expanded, so a fresh run
rewrites about 400 lines of the declaration file with no semantic change.
Measured, not assumed. Do not read that diff as the model having moved --
check ``cube-catalog-meta.json`` for that. Running ``trunk fmt``, or just
committing, settles it back.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_META = REPO_ROOT / "docs" / "reference" / "cube-catalog-meta.json"
DEFAULT_OUT = REPO_ROOT / "docs" / "reference" / "cube-catalog.d.ts"

# Cube dimension type -> the TypeScript type of that member in a /load row.
# Every mart column behind these views is nullable (verified against
# INFORMATION_SCHEMA: 230 of 230), so every value is unioned with null below.
DIMENSION_VALUE_TYPES = {
    "string": "string",
    "boolean": "boolean",
    "time": "TimeDimensionValue",
    "number": "NumericDimensionValue",
}

PREAMBLE = """/**
 * Cube semantic layer -- generated TypeScript surface.
 *
 * GENERATED FILE -- do not edit by hand.
 * Regenerate with `uv run scripts/cube_types_export.py`.
 *
 * Source: docs/reference/cube-catalog-meta.json ({generated_from}).
 * {view_count} views, {measure_count} measures, {dimension_count} dimensions.
 *
 * Query the REST API at `POST {{baseUrl}}/cubejs-api/v1/load` with a JSON body
 * `{{ query: CubeQuery<V> }}`. The `Authorization` header takes the RAW token
 * with no `Bearer` prefix.
 *
 * Two response behaviours these types encode deliberately:
 *
 * - Numeric measures come back as JSON STRINGS (`"900"`, not `900`), so
 *   `MeasureValue` is `string`. Parse before doing arithmetic.
 * - Every member is optional on a row, because a row carries only the members
 *   the query requested, and any of them can be null.
 *
 * One behaviour they cannot encode: an `access_policy` denial blocks the WHOLE
 * query rather than stripping the member you are not entitled to. A query that
 * type-checks can still 403 for a viewer with a narrower scope. Build for that.
 */

/** Granularities accepted on a `timeDimensions` entry. */
export type Granularity =
  | "second"
  | "minute"
  | "hour"
  | "day"
  | "week"
  | "month"
  | "quarter"
  | "year";

/**
 * Numeric measures are serialised as strings by the REST API. Parse with
 * `Number(...)` before arithmetic; do not assume `number`.
 */
export type MeasureValue = string;

/** Time dimensions are serialised as ISO 8601 strings. */
export type TimeDimensionValue = string;

/**
 * Numeric dimensions. Typed permissively: measure stringification is verified,
 * but whether numeric DIMENSIONS are stringified is not, so narrow at the edge
 * rather than trusting one branch of this union.
 */
export type NumericDimensionValue = string | number;

/** Filter operators accepted on a `filters` entry. */
export type FilterOperator =
  | "equals"
  | "notEquals"
  | "contains"
  | "notContains"
  | "startsWith"
  | "endsWith"
  | "gt"
  | "gte"
  | "lt"
  | "lte"
  | "set"
  | "notSet"
  | "inDateRange"
  | "notInDateRange"
  | "beforeDate"
  | "afterDate";
"""

TAIL = """
/** Every view exposed by the semantic layer. */
export type ViewName = {view_union};

/** Member-name unions per view, keyed by view name. */
export interface ViewMembers {{
{view_members}
}}

/** Row shapes per view, keyed by view name. */
export interface ViewRows {{
{view_rows}
}}

/** A filter clause against one member of view `V`. */
export interface CubeFilter<V extends ViewName> {{
  member: ViewMembers[V]["member"];
  operator: FilterOperator;
  /** Omitted for the `set` / `notSet` operators, required otherwise. */
  values?: string[];
}}

/** A time-dimension clause against one time member of view `V`. */
export interface CubeTimeDimension<V extends ViewName> {{
  dimension: ViewMembers[V]["timeDimension"];
  granularity?: Granularity;
  /** `["2025-08-01", "2026-06-30"]`, or a named range such as `"last week"`. */
  dateRange?: [string, string] | string;
}}

/**
 * A `/load` query against view `V`. Member names are checked against the
 * catalog, so a typo or a member from another view fails to compile.
 */
export interface CubeQuery<V extends ViewName> {{
  measures?: ViewMembers[V]["measure"][];
  dimensions?: ViewMembers[V]["dimension"][];
  timeDimensions?: CubeTimeDimension<V>[];
  filters?: CubeFilter<V>[];
  order?: Partial<Record<ViewMembers[V]["member"], "asc" | "desc">>;
  limit?: number;
  offset?: number;
  /** IANA name, e.g. `"America/New_York"`. Defaults to UTC when omitted. */
  timezone?: string;
}}

/** The envelope returned by `POST /cubejs-api/v1/load`. */
export interface CubeLoadResponse<V extends ViewName> {{
  data: ViewRows[V][];
  /** Cube echoes a NORMALISED query here -- not a copy of what you sent. */
  query: CubeQuery<V>;
  annotation: {{
    measures: Record<string, unknown>;
    dimensions: Record<string, unknown>;
    timeDimensions: Record<string, unknown>;
  }};
}}
"""


def pascal_case(view_name: str) -> str:
    """`student_attendance_view` -> `StudentAttendanceView`."""
    return "".join(part.title() for part in view_name.split("_") if part)


def clean_description(raw: str | None) -> str:
    """Collapse a description to a single JSDoc-safe line."""
    if not raw:
        return ""
    # `*/` inside a block comment would terminate it early.
    collapsed = re.sub(r"\s+", " ", raw).strip()
    return collapsed.replace("*/", "*\\/")


def jsdoc(summary: str, description: str | None, indent: str = "  ") -> list[str]:
    """Render a one-or-two-part JSDoc block, or nothing when both are empty."""
    body = clean_description(description)
    if summary and body:
        text = f"{summary} -- {body}"
    else:
        text = summary or body
    if not text:
        return []
    return [f"{indent}/** {text} */"]


def member_union(members: list[dict[str, Any]]) -> str:
    """Render a union of member-name literals, or `never` when there are none."""
    if not members:
        return "never"
    return "\n    | ".join(f'"{m["name"]}"' for m in members)


def render_view(view: dict[str, Any]) -> str:
    """One block of declarations for a single view."""
    name = view["name"]
    alias = pascal_case(name)
    measures = view.get("measures", [])
    dimensions = view.get("dimensions", [])
    time_dimensions = [d for d in dimensions if d.get("type") == "time"]

    lines: list[str] = []
    lines.extend(jsdoc(view.get("title") or name, view.get("description"), ""))
    lines.append(f"export type {alias}Measure =\n    | {member_union(measures)};")
    lines.append("")
    lines.append(f"export type {alias}Dimension =\n    | {member_union(dimensions)};")
    lines.append("")
    lines.append(
        f"export type {alias}TimeDimension =\n    | {member_union(time_dimensions)};"
    )
    lines.append("")
    lines.append(f"export type {alias}Member = {alias}Measure | {alias}Dimension;")
    lines.append("")

    # The row interface: every member optional, every value nullable.
    lines.append(f"/** A `/load` row from `{name}`. */")
    lines.append(f"export interface {alias}Row {{")
    for measure in measures:
        lines.extend(jsdoc(measure.get("shortTitle", ""), measure.get("description")))
        lines.append(f'  "{measure["name"]}"?: MeasureValue | null;')
    for dimension in dimensions:
        value_type = DIMENSION_VALUE_TYPES.get(dimension.get("type", ""), "string")
        lines.extend(
            jsdoc(dimension.get("shortTitle", ""), dimension.get("description"))
        )
        lines.append(f'  "{dimension["name"]}"?: {value_type} | null;')
    lines.append("}")
    return "\n".join(lines)


def render(meta: dict[str, Any]) -> str:
    """Render the whole declaration file."""
    views = meta.get("views", [])
    measure_count = sum(len(v.get("measures", [])) for v in views)
    dimension_count = sum(len(v.get("dimensions", [])) for v in views)

    parts = [
        PREAMBLE.format(
            generated_from=meta.get("generated_from", "unknown"),
            view_count=len(views),
            measure_count=measure_count,
            dimension_count=dimension_count,
        )
    ]
    parts.extend(render_view(view) for view in sorted(views, key=lambda v: v["name"]))

    view_union = "\n  | ".join(f'"{v["name"]}"' for v in views)
    view_members = "\n".join(
        f'  "{v["name"]}": {{\n'
        f"    measure: {pascal_case(v['name'])}Measure;\n"
        f"    dimension: {pascal_case(v['name'])}Dimension;\n"
        f"    timeDimension: {pascal_case(v['name'])}TimeDimension;\n"
        f"    member: {pascal_case(v['name'])}Member;\n"
        f"  }};"
        for v in views
    )
    view_rows = "\n".join(
        f'  "{v["name"]}": {pascal_case(v["name"])}Row;' for v in views
    )
    parts.append(
        TAIL.format(
            view_union=f"\n  | {view_union}",
            view_members=view_members,
            view_rows=view_rows,
        )
    )
    return "\n\n".join(parts).rstrip() + "\n"


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
    parser.add_argument("--meta", type=Path, default=DEFAULT_META)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    meta = json.loads(args.meta.read_text(encoding="utf-8"))
    views = meta.get("views", [])

    # Same guard as the catalog export, for the same reason: an access-denied
    # snapshot and an undeployed model both look like zero views, and only one
    # of them is worth writing to disk.
    if not views:
        print(
            f"No views in {args.meta}. Regenerate the catalog with "
            "cube_catalog_export.py as a network-scoped identity first. "
            "Nothing written.",
            file=sys.stderr,
        )
        return 1

    args.out.write_text(render(meta), encoding="utf-8")

    measures = sum(len(v.get("measures", [])) for v in views)
    dimensions = sum(len(v.get("dimensions", [])) for v in views)
    print(
        f"Wrote {_display(args.out)}: "
        f"{len(views)} views, {measures} measures, {dimensions} dimensions"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

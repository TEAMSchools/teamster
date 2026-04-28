# /// script
# requires-python = ">=3.13"
# dependencies = ["pyyaml>=6.0"]
# ///

"""Generate the column naming audit inventory CSV.

Reads every YAML properties file under the kipptaf mart directories
(bridges/dimensions/facts) and emits one CSV row per (model, column) pair
plus pre-populated structural-addition rows for `dim_students` and
`dim_staff`.

Output: docs/superpowers/specs/2026-04-15-column-naming-audit-inventory.csv

Usage:
    uv run scripts/gen_column_naming_audit_inventory.py

Design reference:
    docs/superpowers/specs/2026-04-15-column-naming-audit.md
"""

from __future__ import annotations

import csv
import difflib
import re
from pathlib import Path
from typing import TextIO

import yaml

_WS_RE = re.compile(r"\s+")


def _flatten_description(text: str | None) -> str:
    """Collapse whitespace runs to single spaces and strip edges."""
    if not text:
        return ""
    return _WS_RE.sub(" ", text).strip()


_DOMAIN_RULES: tuple[tuple[str, str], ...] = (
    # (substring-in-model-name, domain). Order matters — first match wins.
    ("staff_observation", "Observation"),
    ("staff_attrition", "Staff"),
    ("staff_benefits", "Staff"),
    ("staff_membership", "Staff"),
    ("staff_status", "Staff"),
    ("staff_work_assignment", "Staff"),
    ("work_assignment", "Staff"),
    ("staffing", "Staffing"),
    ("student_attendance", "Attendance"),
    ("student_contact", "Student"),
    ("student_section_enrollment", "Student"),
    ("student_enrollment", "Student"),
    ("student_assessment_expectation", "Assessment"),
    ("behavioral", "Behavioral"),
    ("family_communication", "Behavioral"),
    ("grade", "Gradebook"),
    ("assessment", "Assessment"),
    ("college", "College"),
    ("survey", "Survey"),
    ("course", "Course"),
    ("job_candidate", "Talent"),
    ("job_posting", "Talent"),
    ("support_ticket", "IT"),
    ("student", "Student"),
    ("staff", "Staff"),
)

_CONFORMED_MODELS = frozenset(
    [
        "dim_dates",
        "dim_locations",
        "dim_regions",
        "dim_school_calendars",
        "dim_terms",
    ]
)


def _domain_for_model(model_name: str) -> str:
    """Classify a mart model name into an audit-review domain."""
    if model_name in _CONFORMED_MODELS:
        return "Conformed"
    for substring, domain in _DOMAIN_RULES:
        if substring in model_name:
            return domain
    return "Uncategorized"


_PLUMBING_COLUMNS: frozenset[str] = frozenset(
    [
        "_dbt_source_relation",
    ]
)


_SOURCE_PREFIXES: tuple[str, ...] = (
    "deanslist_",
    "powerschool_",
)

_SOURCE_TERMS: frozenset[str] = frozenset(
    [
        "sam_account_name",
        "sections_dcid",
        "teachernumber",
    ]
)

_KIPP_TERMS: tuple[str, ...] = (
    "employee_number",
    "microgoal",
    "teammate",
)


def _check_naming_rules(col_name: str) -> tuple[str, str] | None:
    """Check a column name against pattern-based naming rules.

    Returns (rule_ref, reviewer_note) if a rule matches, else None.
    """
    # R1: source-system prefixes
    for prefix in _SOURCE_PREFIXES:
        if col_name.startswith(prefix):
            return ("R1", f"source-system prefix: {prefix}")

    # R1: source-system exact terms
    if col_name in _SOURCE_TERMS:
        return ("R1", "source-system term")

    # R2: KIPP-specific jargon (substring match)
    for term in _KIPP_TERMS:
        if term in col_name:
            return ("R2", f"KIPP-specific term: {term}")

    return None


def _load_attribute_extract(fh: TextIO) -> dict[str, list[dict[str, str]]]:
    """Load an attribute CSV (Ed-Fi or CEDS) into a lookup dict.

    Returns {attribute_snake: [{entity, attribute_camel, description}, ...]}.
    """
    result: dict[str, list[dict[str, str]]] = {}
    reader = csv.DictReader(fh)
    for row in reader:
        snake = row["attribute_snake"]
        result.setdefault(snake, []).append(
            {
                "entity": row["entity"],
                "attribute_camel": row["attribute_camel"],
                "description": row["description"],
            }
        )
    return result


def _exact_match(
    col_name: str,
    attrs: dict[str, list[dict[str, str]]],
    label: str,
) -> tuple[str, str] | None:
    """Tier 1: exact token-set match against a standard's attributes.

    Returns (proposed_name, reviewer_note) or None.
    """
    col_tokens = frozenset(col_name.split("_"))
    for snake, entries in attrs.items():
        if frozenset(snake.split("_")) == col_tokens:
            parts = []
            for e in entries:
                desc_preview = e["description"][:80] if e["description"] else ""
                parts.append(f"{e['entity']}.{e['attribute_camel']} — {desc_preview}")
            return (snake, f"{label} exact: " + "; ".join(parts))
    return None


def _fuzzy_match(
    col_name: str,
    attrs: dict[str, list[dict[str, str]]],
    label: str,
    threshold: float = 0.6,
    max_candidates: int = 3,
) -> str | None:
    """Tier 2: fuzzy match using SequenceMatcher.

    Returns a reviewer_note string with candidates, or None.
    """
    candidates: list[tuple[float, str, list[dict[str, str]]]] = []
    for snake, entries in attrs.items():
        ratio = difflib.SequenceMatcher(None, col_name, snake).ratio()
        if ratio >= threshold:
            candidates.append((ratio, snake, entries))

    if not candidates:
        return None

    candidates.sort(key=lambda c: c[0], reverse=True)
    top = candidates[:max_candidates]

    parts = []
    for _ratio, snake, entries in top:
        for e in entries:
            desc_preview = e["description"][:80] if e["description"] else ""
            parts.append(
                f"{snake} ({e['entity']}.{e['attribute_camel']} — {desc_preview})"
            )
    return f"{label} candidates: " + "; ".join(parts)


def _join_notes(existing: str, new: str) -> str:
    """Join reviewer notes with a separator."""
    if not existing:
        return new
    return f"{existing}. {new}"


def _append_standard_notes(
    row: dict[str, str],
    col_name: str,
    attrs: dict[str, list[dict[str, str]]],
    label: str,
    allow_action: bool,
) -> bool:
    """Append one standard's matching notes to a row.

    When `allow_action` is True and the row is still unrouted
    (action=keep with no rule_ref), an exact match sets action=rename
    and rule_ref=R6, and a fuzzy match sets rule_ref=R6 alone.
    Otherwise notes are appended as informational candidates.

    Returns True if the row was routed to a rename/rule action by this
    call, so subsequent standards can downgrade to informational mode.
    """
    if allow_action:
        exact = _exact_match(col_name, attrs, label)
        if exact is not None:
            proposed, note = exact
            if proposed != col_name:
                row["action"] = "rename"
                row["proposed_name"] = proposed
            row["rule_ref"] = "R6"
            row["reviewer_notes"] = _join_notes(row.get("reviewer_notes", ""), note)
            return True
        fuzzy = _fuzzy_match(col_name, attrs, label)
        if fuzzy is not None:
            row["rule_ref"] = "R6"
            row["reviewer_notes"] = _join_notes(row.get("reviewer_notes", ""), fuzzy)
            return True
        return False

    exact = _exact_match(col_name, attrs, label)
    if exact is not None:
        row["reviewer_notes"] = _join_notes(row.get("reviewer_notes", ""), exact[1])
        return False
    fuzzy = _fuzzy_match(col_name, attrs, label)
    if fuzzy is not None:
        row["reviewer_notes"] = _join_notes(row.get("reviewer_notes", ""), fuzzy)
    return False


def _append_all_standard_notes(
    row: dict[str, str],
    col_name: str,
    standards: list[tuple[str, dict[str, list[dict[str, str]]]]],
) -> None:
    """Append Ed-Fi then CEDS matching notes.

    Ed-Fi is primary for auto-rename/rule-ref routing (R6). CEDS is
    always additive — once Ed-Fi has routed the row (or on every row
    once routing is off), CEDS candidates are appended as
    informational notes only.
    """
    existing_action = row.get("action", "keep")
    routed = existing_action != "keep" or bool(row.get("rule_ref"))
    for label, attrs in standards:
        this_routed = _append_standard_notes(
            row,
            col_name,
            attrs,
            label=label,
            allow_action=not routed,
        )
        routed = routed or this_routed


Standards = list[tuple[str, dict[str, list[dict[str, str]]]]]


def _read_mart_yaml(
    path: Path, standards: Standards | None = None
) -> list[dict[str, str]]:
    """Parse a single mart properties YAML into audit-row dicts."""
    with path.open(encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)

    plumbing = _PLUMBING_COLUMNS
    rows: list[dict[str, str]] = []

    for model in doc.get("models", []) or []:
        model_name = model["name"]
        domain = _domain_for_model(model_name)
        for column in model.get("columns", []) or []:
            col_name = column["name"]
            meta = column.get("config", {}).get("meta", {})
            row: dict[str, str] = {
                "domain": domain,
                "model": model_name,
                "current_column": col_name,
                "data_type": column.get("data_type", "") or "",
                "current_description": _flatten_description(column.get("description")),
                "source_system": meta.get("source_system", ""),
                "source_model": meta.get("source_model", ""),
                "source_column": meta.get("source_column", ""),
                "column_role": meta.get("column_role", ""),
                "action": "keep",
                "proposed_name": "",
                "rule_ref": "",
                "review_status": "not_reviewed",
                "reviewer_notes": "",
            }

            if col_name in plumbing:
                row["action"] = "remove"
                row["rule_ref"] = "plumbing"
            elif row["column_role"] == "foreign_key":
                row["action"] = "remove"
                row["rule_ref"] = "plumbing"
                row["reviewer_notes"] = "source-system FK"
            elif row["column_role"] == "primary_key":
                row["action"] = "remove"
                row["rule_ref"] = "plumbing"
                row["reviewer_notes"] = "source-system PK"
            else:
                rule = _check_naming_rules(col_name)
                if rule is not None:
                    rule_ref, note = rule
                    row["action"] = "rename"
                    row["rule_ref"] = rule_ref
                    row["reviewer_notes"] = note
                elif (
                    row["source_column"]
                    and row["source_column"] == col_name
                    and not col_name.endswith("_key")
                ):
                    row["action"] = "rename"
                    row["rule_ref"] = "R1"
                    row["reviewer_notes"] = (
                        f"source-system passthrough from "
                        f"{row['source_system']} {row['source_model']}"
                    )

            if standards is not None:
                _append_all_standard_notes(row, col_name, standards)

            rows.append(row)

    return rows


CSV_FIELDS: tuple[str, ...] = (
    "domain",
    "model",
    "current_column",
    "data_type",
    "current_description",
    "source_system",
    "source_model",
    "source_column",
    "column_role",
    "action",
    "proposed_name",
    "rule_ref",
    "review_status",
    "reviewer_notes",
)

MART_YAML_DIRS: tuple[Path, ...] = (
    Path("src/dbt/kipptaf/models/marts/bridges/properties"),
    Path("src/dbt/kipptaf/models/marts/dimensions/properties"),
    Path("src/dbt/kipptaf/models/marts/facts/properties"),
)

OUTPUT_CSV = Path("docs/superpowers/specs/2026-04-15-column-naming-audit-inventory.csv")
EDFI_CSV = Path("docs/superpowers/specs/edfi-v6.1.0-attributes.csv")
CEDS_CSV = Path("docs/superpowers/specs/ceds-v14.0.0.0-attributes.csv")

_PRESERVED_FIELDS: tuple[str, ...] = (
    "action",
    "proposed_name",
    "rule_ref",
    "review_status",
    "reviewer_notes",
)


def _load_prior_decisions(
    path: Path,
) -> dict[tuple[str, str], dict[str, str]]:
    """Read an existing inventory and capture approved-row decisions.

    Returns {(model, current_column): {action, proposed_name, rule_ref,
    review_status, reviewer_notes}} for rows where review_status is
    anything other than 'not_reviewed' or empty.
    """
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        preserved: dict[tuple[str, str], dict[str, str]] = {}
        for row in reader:
            status = row.get("review_status", "") or ""
            if status in ("", "not_reviewed"):
                continue
            key = (row["model"], row["current_column"])
            preserved[key] = {field: row.get(field, "") for field in _PRESERVED_FIELDS}
    return preserved


def _overlay_prior_decisions(
    rows: list[dict[str, str]],
    preserved: dict[tuple[str, str], dict[str, str]],
) -> int:
    """Overwrite generated fields with previously-approved values."""
    applied = 0
    for row in rows:
        key = (row["model"], row["current_column"])
        if key in preserved:
            for field in _PRESERVED_FIELDS:
                row[field] = preserved[key][field]
            applied += 1
    return applied


def _sort_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Stable sort by (domain, model). Within a model, YAML order is kept."""
    return sorted(rows, key=lambda r: (r["domain"], r["model"]))


def _infer_dimension(fk_name: str) -> str | None:
    """Infer a dimension model name from a FK column name.

    'student_key' → 'dim_students'
    'student_enrollment_key' → 'dim_student_enrollments'
    'term_key' → 'dim_terms'
    'date_key' → 'dim_dates'
    """
    if not fk_name.endswith("_key"):
        return None
    stem = fk_name[: -len("_key")]
    # Try plural first (most common), then singular
    for suffix in ("s", ""):
        candidate = f"dim_{stem}{suffix}"
        if candidate in _CONFORMED_MODELS or candidate.startswith("dim_"):
            return candidate
    return f"dim_{stem}s"


def _apply_r9(rows: list[dict[str, str]]) -> int:
    """Flag redundant columns (R9) reachable via FK joins to dimensions.

    A non-key column on a fact/bridge is redundant if a FK in the same
    model points to a dimension that contains a column with the same
    source_column provenance.

    Mutates rows in place. Returns the number flagged.
    """
    # Build dimension provenance: {dim_name: {source_column: dim_col_name}}
    dim_provenance: dict[str, dict[str, str]] = {}
    for row in rows:
        model = row["model"]
        if model.startswith("dim_") and row["source_column"]:
            dim_provenance.setdefault(model, {})[row["source_column"]] = row[
                "current_column"
            ]

    # For each model, find FKs and check non-FK columns
    # Group rows by model
    by_model: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_model.setdefault(row["model"], []).append(row)

    flagged = 0
    for model_name, model_rows in by_model.items():
        if not (model_name.startswith("fct_") or model_name.startswith("bridge_")):
            continue

        # Find FK columns and their target dimensions
        fk_dims: list[str] = []
        for row in model_rows:
            if row["current_column"].endswith("_key"):
                dim = _infer_dimension(row["current_column"])
                if dim and dim in dim_provenance:
                    fk_dims.append(dim)

        if not fk_dims:
            continue

        # Check non-FK columns with provenance
        for row in model_rows:
            col = row["current_column"]
            if col.endswith("_key") or not row["source_column"]:
                continue
            # Already flagged by another rule
            if row["action"] == "remove":
                continue

            src_col = row["source_column"]
            for dim in fk_dims:
                if src_col in dim_provenance[dim]:
                    dim_col = dim_provenance[dim][src_col]
                    row["action"] = "remove"
                    row["rule_ref"] = "R9"
                    row["reviewer_notes"] = _join_notes(
                        row["reviewer_notes"],
                        f"reachable via FK → {dim}.{dim_col}",
                    )
                    flagged += 1
                    break

    return flagged


def _write_csv(rows: list[dict[str, str]], fh: TextIO) -> None:
    writer = csv.DictWriter(fh, fieldnames=list(CSV_FIELDS), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in CSV_FIELDS})


def main() -> None:
    standards: Standards = []
    for label, path in (("Ed-Fi", EDFI_CSV), ("CEDS", CEDS_CSV)):
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as fh:
            attrs = _load_attribute_extract(fh)
        standards.append((label, attrs))
        print(f"Loaded {sum(len(v) for v in attrs.values())} {label} attributes")

    preserved = _load_prior_decisions(OUTPUT_CSV)
    if preserved:
        print(f"Preserving {len(preserved)} previously-reviewed rows")

    rows: list[dict[str, str]] = []
    for directory in MART_YAML_DIRS:
        for yaml_path in sorted(directory.glob("*.yml")):
            rows.extend(_read_mart_yaml(yaml_path, standards=standards or None))
    r9_count = _apply_r9(rows)
    if r9_count:
        print(f"Flagged {r9_count} redundant columns (R9)")

    applied = _overlay_prior_decisions(rows, preserved)
    if applied:
        print(f"Overlaid {applied} preserved decisions")

    sorted_rows = _sort_rows(rows)

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        _write_csv(sorted_rows, fh)

    print(f"Wrote {len(sorted_rows)} rows to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()

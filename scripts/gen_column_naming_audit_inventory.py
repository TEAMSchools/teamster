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


def _load_edfi_extract(fh: TextIO) -> dict[str, list[dict[str, str]]]:
    """Load the vendored Ed-Fi attribute CSV into a lookup dict.

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


def _edfi_exact_match(
    col_name: str, edfi: dict[str, list[dict[str, str]]]
) -> tuple[str, str] | None:
    """Tier 1: exact token-set match against Ed-Fi attributes.

    Returns (proposed_name, reviewer_note) or None.
    """
    col_tokens = frozenset(col_name.split("_"))
    for snake, entries in edfi.items():
        edfi_tokens = frozenset(snake.split("_"))
        if col_tokens == edfi_tokens:
            parts = []
            for e in entries:
                desc_preview = e["description"][:80] if e["description"] else ""
                parts.append(f"{e['entity']}.{e['attribute_camel']} — {desc_preview}")
            note = "Ed-Fi exact: " + "; ".join(parts)
            return (snake, note)
    return None


def _edfi_fuzzy_match(
    col_name: str,
    edfi: dict[str, list[dict[str, str]]],
    threshold: float = 0.6,
    max_candidates: int = 3,
) -> str | None:
    """Tier 2: fuzzy match using SequenceMatcher.

    Returns a reviewer_note string with candidates, or None.
    """
    candidates: list[tuple[float, str, list[dict[str, str]]]] = []
    for snake, entries in edfi.items():
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
    return "Ed-Fi candidates: " + "; ".join(parts)


def _join_notes(existing: str, new: str) -> str:
    """Join reviewer notes with a separator."""
    if not existing:
        return new
    return f"{existing}. {new}"


def _append_edfi_notes(
    row: dict[str, str],
    col_name: str,
    edfi: dict[str, list[dict[str, str]]],
) -> None:
    """Append Ed-Fi matching notes to a row's reviewer_notes.

    If the row has no action from another rule, exact matches set
    action=rename and fuzzy matches add candidates. If another rule
    already set the action, Ed-Fi candidates are appended as
    informational notes.
    """
    existing_action = row.get("action", "keep")

    if existing_action == "keep" and not row.get("rule_ref"):
        exact = _edfi_exact_match(col_name, edfi)
        if exact is not None:
            proposed, note = exact
            if proposed != col_name:
                row["action"] = "rename"
                row["proposed_name"] = proposed
            row["rule_ref"] = "R6"
            row["reviewer_notes"] = _join_notes(row.get("reviewer_notes", ""), note)
            return

        fuzzy = _edfi_fuzzy_match(col_name, edfi)
        if fuzzy is not None:
            row["rule_ref"] = "R6"
            row["reviewer_notes"] = _join_notes(row.get("reviewer_notes", ""), fuzzy)
            return
    else:
        exact = _edfi_exact_match(col_name, edfi)
        if exact is not None:
            _, note = exact
            row["reviewer_notes"] = _join_notes(row.get("reviewer_notes", ""), note)
            return

        fuzzy = _edfi_fuzzy_match(col_name, edfi)
        if fuzzy is not None:
            row["reviewer_notes"] = _join_notes(row.get("reviewer_notes", ""), fuzzy)


def _read_mart_yaml(
    path: Path, edfi: dict[str, list[dict[str, str]]] | None = None
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
            else:
                rule = _check_naming_rules(col_name)
                if rule is not None:
                    rule_ref, note = rule
                    row["action"] = "rename"
                    row["rule_ref"] = rule_ref
                    row["reviewer_notes"] = note

            if edfi is not None:
                _append_edfi_notes(row, col_name, edfi)

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
    writer = csv.DictWriter(fh, fieldnames=list(CSV_FIELDS))
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in CSV_FIELDS})


def main() -> None:
    edfi: dict[str, list[dict[str, str]]] | None = None
    if EDFI_CSV.exists():
        with EDFI_CSV.open(encoding="utf-8") as fh:
            edfi = _load_edfi_extract(fh)
        print(f"Loaded {sum(len(v) for v in edfi.values())} Ed-Fi attributes")

    rows: list[dict[str, str]] = []
    for directory in MART_YAML_DIRS:
        for yaml_path in sorted(directory.glob("*.yml")):
            rows.extend(_read_mart_yaml(yaml_path, edfi=edfi))
    r9_count = _apply_r9(rows)
    if r9_count:
        print(f"Flagged {r9_count} redundant columns (R9)")
    sorted_rows = _sort_rows(rows)

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        _write_csv(sorted_rows, fh)

    print(f"Wrote {len(sorted_rows)} rows to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()

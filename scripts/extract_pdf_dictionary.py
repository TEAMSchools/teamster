# /// script
# requires-python = ">=3.13"
# dependencies = ["pypdf>=4.0", "pyyaml>=6.0"]
# ///

"""Extract column descriptions from source-system PDF data dictionaries.

Reads a PDF data dictionary (PowerSchool or ADP), extracts field descriptions,
matches them to staging YAML column names, and outputs a JSON mapping file.

Output: .claude/scratch/<source>_dictionary.json

Usage:
    uv run scripts/extract_pdf_dictionary.py <pdf_path> <source_system>

    source_system: "powerschool" or "adp"

Design reference:
    docs/superpowers/specs/2026-04-16-data-dictionary-enrichment-design.md
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml


def pascal_to_snake(name: str) -> str:
    """Convert PascalCase or MixedCase to snake_case.

    Handles:
    - StudentNumber -> student_number
    - DCid -> dcid
    - SSN -> ssn
    - Alert_Discipline -> alert_discipline
    - StudentID -> student_id
    - GPAPoints -> gpa_points
    """
    # If already all lowercase (possibly with underscores), return as-is
    if name == name.lower():
        return name

    # Split on existing underscores, convert each segment
    parts = name.split("_")
    converted_parts: list[str] = []

    for part in parts:
        if not part:
            converted_parts.append("")
            continue
        s = part
        # Insert underscore before uppercase that follows lowercase/digit
        s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
        # Insert underscore before cap+lowercase that follows multiple caps,
        # but only if the preceding caps form a longer acronym (3+ chars)
        # This handles "GPAPoints" -> "GPA_Points" but not "DCid" -> "D_Cid"

        def replace_caps(match: re.Match[str]) -> str:
            group1 = match.group(1)  # Preceding caps
            group2 = match.group(2)  # Cap + lowercase
            if len(group1) >= 3:
                return group1 + "_" + group2
            return match.group(0)

        s = re.sub(r"([A-Z]+)([A-Z][a-z])", replace_caps, s)
        converted_parts.append(s.lower())

    return "_".join(converted_parts)


def camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case.

    Handles:
    - birthDate -> birth_date
    - genderCode -> gender_code
    - emailURI -> email_uri
    - countrySubdivisionLevel1 -> country_subdivision_level_1
    """
    # If already snake_case, return as-is
    if name == name.lower() and "_" in name:
        return name

    # Insert underscore before transitions
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    # Also split between letters and trailing digits
    s = re.sub(r"([a-zA-Z])(\d)", r"\1_\2", s)
    return s.lower()


# PII column name patterns (checked against snake_case column name)
_PII_NAME_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(^|_)(first|last|middle|given|family|nick)_?name", re.IGNORECASE),
    re.compile(r"(^|_)formatted_name", re.IGNORECASE),
    re.compile(r"(^|_)lastfirst($|_)", re.IGNORECASE),
    re.compile(r"(^|_)dob($|_)", re.IGNORECASE),
    re.compile(r"birth_date", re.IGNORECASE),
    re.compile(r"(^|_)ssn($|_)", re.IGNORECASE),
    re.compile(r"social_security", re.IGNORECASE),
    re.compile(r"(^|_)(street|city|zip|postal_code|city_name)($|_)", re.IGNORECASE),
    re.compile(r"(^|_)line_(one|two|three)($|_)", re.IGNORECASE),
    re.compile(r"(^|_)(home_)?phone($|_)", re.IGNORECASE),
    re.compile(r"dial_number", re.IGNORECASE),
    re.compile(r"(^|_)fax($|_)", re.IGNORECASE),
    re.compile(r"guardian(email|fax|phone)", re.IGNORECASE),
    re.compile(r"email_uri", re.IGNORECASE),
    re.compile(r"(^|_)email($|_)", re.IGNORECASE),
    re.compile(r"state_studentnumber", re.IGNORECASE),
    re.compile(r"web_password", re.IGNORECASE),
    re.compile(r"emerg_contact", re.IGNORECASE),
)

# PII description keywords (checked against description text)
_PII_DESC_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"social\s+security", re.IGNORECASE),
    re.compile(r"date\s+of\s+birth", re.IGNORECASE),
    re.compile(r"home\s+address", re.IGNORECASE),
    re.compile(r"emergency\s+contact", re.IGNORECASE),
    re.compile(r"phone\s+number", re.IGNORECASE),
    re.compile(r"email\s+address", re.IGNORECASE),
    re.compile(r"\bSSN\b"),
    re.compile(r"\bDOB\b"),
)


def classify_pii(column_name: str, description: str) -> bool:
    """Classify whether a column contains PII.

    Returns True for names, dates of birth, SSN/tax IDs, addresses,
    phone numbers, email addresses, government IDs, passwords,
    and emergency contacts.
    """
    for pattern in _PII_NAME_PATTERNS:
        if pattern.search(column_name):
            return True
    for pattern in _PII_DESC_PATTERNS:
        if pattern.search(description):
            return True
    return False


# Matches table name headers like:
#   "Students, 167 (ver3.6.1)"
#   "CC (ver3.6.1)"
#   "AssignmentScore, 2 (ver3.6.1)"
_PS_TABLE_HEADER_RE = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*)(?:,\s*\d+)?\s+\(ver\d+\.\d+(?:\.\d+)*\)\s*$",
    re.MULTILINE,
)


def extract_ps_table_name(page_text: str) -> str | None:
    """Extract the PowerSchool table name from a page's text.

    Table name headers appear as footers: 'TableName, N (verX.Y.Z)' or
    'TableName (verX.Y.Z)'. Returns the table name or None if not found.
    """
    match = _PS_TABLE_HEADER_RE.search(page_text)
    if match:
        return match.group(1)
    return None


_PS_COL_HEADER_RE = re.compile(
    r"^Column\s+Name\s+(?:Initial\s*Version|InitialVersion)\s+Data\s+Type\s+Description",
    re.MULTILINE,
)


def extract_ps_table_description(page_text: str) -> str | None:
    """Extract the table-level description paragraph from a PS PDF page.

    The description appears between the page number and the 'Column Name
    InitialVersion Data Type Description' header. Returns None if no
    description is found (e.g., continuation pages).
    """
    col_header = _PS_COL_HEADER_RE.search(page_text)
    if col_header is None:
        return None

    # Text before the column header, after the page number line
    preamble = page_text[: col_header.start()].strip()
    lines = preamble.split("\n")

    # Skip the first line (page number) and any blank lines
    desc_lines = [
        line.strip()
        for line in lines[1:]
        if line.strip() and not line.strip().isdigit()
    ]
    if not desc_lines:
        return None

    description = " ".join(desc_lines)
    # Skip if it looks like a table name header, not a description
    if _PS_TABLE_HEADER_RE.match(description):
        return None
    return description


# Matches column entry lines like:
#   "ColumnName 3.6.1 DataType(size) Description text..."
# Version: digits.digits[.digits]*
# Data type: word characters, optional parenthesized size like (10,0)
_PS_COLUMN_RE = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*)\s+"  # column name
    r"(\d+\.\d+(?:\.\d+)*)\s+"  # version
    r"([A-Za-z0-9]+(?:\([^)]*\))?)\s+"  # data type (with optional size)
    r"(.+)$"  # description (rest of line)
)

# Lines to skip
_PS_SKIP_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^Column\s+Name\s+InitialVersion\s+Data\s+Type\s+Description"),
    re.compile(r"^\d+$"),  # page numbers
    _PS_TABLE_HEADER_RE,
    re.compile(r"PowerSchool\s+Private\s+Information"),
    re.compile(r"^\s*$"),  # blank lines
)


def parse_ps_columns(page_text: str) -> list[dict[str, str]]:
    """Parse PowerSchool column entries from PDF page text.

    Returns a list of dicts with keys: source_column, description.
    Skips header lines, page numbers, table footers, and confidentiality
    notices.
    """
    entries: list[dict[str, str]] = []

    for line in page_text.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Skip known non-column lines
        skip = False
        for pattern in _PS_SKIP_PATTERNS:
            if pattern.match(line):
                skip = True
                break
        if skip:
            continue

        # Skip table description paragraphs (no version number pattern)
        match = _PS_COLUMN_RE.match(line)
        if match:
            # Fix word-join artifacts from pypdf text extraction
            # (adjacent text streams lose spaces: "notguaranteed")
            desc = re.sub(r"([a-z])([A-Z])", r"\1 \2", match.group(4).strip())
            entries.append(
                {
                    "source_column": match.group(1),
                    "description": desc,
                }
            )

    return entries


# Directories containing PowerSchool staging YAML files
PS_YAML_DIRS: tuple[Path, ...] = (
    Path("src/dbt/powerschool/models/sis/staging/properties"),
    Path("src/dbt/kipptaf/models/powerschool/staging/properties"),
)


def ps_table_to_model_name(table_name: str) -> str:
    """Convert a PowerSchool PDF table name to a dbt staging model name.

    Examples:
        Students -> stg_powerschool__students
        CC -> stg_powerschool__cc
        S_NJ_STU_X -> stg_powerschool__s_nj_stu_x
        StoredGrades -> stg_powerschool__storedgrades
    """
    return f"stg_powerschool__{table_name.lower()}"


def build_ps_yaml_index() -> dict[str, set[str]]:
    """Build an index of model_name -> set of column names from PS YAMLs.

    Scans all PowerSchool staging YAML directories and collects column names
    for each model. If the same model appears in multiple directories,
    columns are merged.
    """
    index: dict[str, set[str]] = {}

    for directory in PS_YAML_DIRS:
        if not directory.exists():
            continue
        for yaml_path in sorted(directory.glob("stg_powerschool__*.yml")):
            with yaml_path.open(encoding="utf-8") as fh:
                doc = yaml.safe_load(fh)
            if not doc:
                continue
            for model in doc.get("models", []) or []:
                model_name = model["name"]
                columns = {
                    col["name"]
                    for col in (model.get("columns", []) or [])
                    if not col["name"].startswith("_dagster_")
                }
                if model_name in index:
                    index[model_name].update(columns)
                else:
                    index[model_name] = columns

    return index


def build_ps_mapping(
    pages: list[str],
    yaml_index: dict[str, set[str]],
) -> dict:
    """Build the PowerSchool PDF-to-YAML mapping.

    Args:
        pages: List of text strings, one per PDF page.
        yaml_index: Model name -> set of column names from YAML files.

    Returns:
        Mapping dict with entries, unmatched lists, and stats.
    """
    # Collect all (table_name, column_entries) from pages.
    # Table name headers appear on the first page of each table section.
    # Continuation pages have column entries but no header — they inherit
    # the most recent table name.
    table_columns: dict[str, list[dict[str, str]]] = {}
    table_descriptions: dict[str, str] = {}
    current_table: str | None = None

    for page_text in pages:
        detected_table = extract_ps_table_name(page_text)
        if detected_table is not None:
            current_table = detected_table
            # Capture table-level description (only on the first page)
            if current_table not in table_descriptions:
                desc = extract_ps_table_description(page_text)
                if desc:
                    table_descriptions[current_table] = desc

        entries = parse_ps_columns(page_text)
        if entries and current_table is not None:
            if current_table not in table_columns:
                table_columns[current_table] = []
            table_columns[current_table].extend(entries)

    # Match against YAML index
    matched_entries: list[dict] = []
    unmatched_pdf: list[dict[str, str]] = []
    all_matched_yaml_columns: dict[str, set[str]] = {}

    for table_name, col_entries in table_columns.items():
        model_name = ps_table_to_model_name(table_name)
        yaml_columns = yaml_index.get(model_name, set())

        for entry in col_entries:
            pdf_col = entry["source_column"]
            snake_col = pascal_to_snake(pdf_col)
            lower_col = pdf_col.lower()
            description = entry.get("description", "")

            # Try snake_case first, then raw lowercase (PS staging YAMLs
            # use lowercased DB column names without underscore insertion)
            matched_col = None
            if snake_col in yaml_columns:
                matched_col = snake_col
            elif lower_col in yaml_columns:
                matched_col = lower_col

            if matched_col is not None:
                matched_entries.append(
                    {
                        "source_table": table_name,
                        "source_column": pdf_col,
                        "model": model_name,
                        "column": matched_col,
                        "description": description,
                        "contains_pii": classify_pii(matched_col, description),
                    }
                )
                if model_name not in all_matched_yaml_columns:
                    all_matched_yaml_columns[model_name] = set()
                all_matched_yaml_columns[model_name].add(matched_col)
            else:
                unmatched_pdf.append({"table": table_name, "column": pdf_col})

    # Find unmatched YAML columns
    unmatched_yaml: list[dict[str, str]] = []
    for model_name, yaml_cols in yaml_index.items():
        matched_cols = all_matched_yaml_columns.get(model_name, set())
        for col in sorted(yaml_cols - matched_cols):
            unmatched_yaml.append({"model": model_name, "column": col})

    # Compute total PDF entries
    total_pdf = sum(len(cols) for cols in table_columns.values())
    total_yaml = sum(len(cols) for cols in yaml_index.values())

    return {
        "source": "powerschool",
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "pdf_entries": total_pdf,
            "yaml_columns": total_yaml,
            "matched": len(matched_entries),
            "unmatched_pdf": len(unmatched_pdf),
            "unmatched_yaml": len(unmatched_yaml),
        },
        "table_descriptions": {
            ps_table_to_model_name(t): d for t, d in table_descriptions.items()
        },
        "entries": matched_entries,
        "unmatched_pdf": unmatched_pdf,
        "unmatched_yaml": unmatched_yaml,
    }


# Matches ADP data dictionary lines like:
#   "/workers/person/birthDate Birth Date Masked by default. Y"
# Schema path starts with /workers/, then field name(s), optional note, Y/NA
_ADP_ENTRY_RE = re.compile(
    r"^(/workers/\S+)\s+"  # schema path
    r"(.+?)\s+"  # field name + optional note (greedy middle)
    r"(Y|NA)\s*$"  # WFN Next Gen flag
)


def parse_adp_entries(page_text: str) -> list[dict[str, str]]:
    """Parse ADP data dictionary entries from PDF page text.

    Returns a list of dicts with keys: schema_path, field_name, description.
    The description includes the field name and any note text.
    """
    entries: list[dict[str, str]] = []

    for line in page_text.split("\n"):
        line = line.strip()
        if not line:
            continue

        match = _ADP_ENTRY_RE.match(line)
        if not match:
            continue

        schema_path = match.group(1)
        middle_text = match.group(2).strip()

        # The middle text contains the field name and optionally a note.
        # Always extract the field name using the heuristic; use the full
        # middle text as the description (which may include the note).
        field_name = _extract_field_name(middle_text)
        description = middle_text

        entries.append(
            {
                "schema_path": schema_path,
                "field_name": field_name,
                "description": description,
            }
        )

    return entries


_ADP_NOTE_START_WORDS: frozenset[str] = frozenset(
    {
        "masked",
        "required",
        "a",
        "an",
        "the",
        "if",
        "not",
        "only",
        "used",
        "this",
    }
)


def _extract_field_name(text: str) -> str:
    """Extract the field name label from ADP middle text.

    The field name is typically 1-4 capitalized words at the start,
    before any note text (which often starts with a verb or lowercase).
    """
    words = text.split()
    field_words: list[str] = []
    for i, word in enumerate(words):
        if i > 0:
            # Stop at any known note-starter word (case-insensitive)
            if word.lower() in _ADP_NOTE_START_WORDS:
                break
            # Stop if word is lowercase (start of note prose)
            if word[0].islower():
                break
        field_words.append(word.rstrip("."))
        if len(field_words) >= 5:
            break
    return " ".join(field_words) if field_words else text


# Directories containing ADP staging YAML files
ADP_YAML_DIRS: tuple[Path, ...] = (
    Path("src/dbt/kipptaf/models/adp/workforce_now/api/staging/properties"),
)


def adp_path_to_column(schema_path: str) -> str:
    """Convert an ADP JSON path to a staging YAML column name.

    Strips the /workers/ prefix, converts each remaining camelCase segment
    to snake_case, and joins with '__'.

    Examples:
        /workers/person/birthDate -> person__birth_date
        /workers/workerDates/originalHireDate -> worker_dates__original_hire_date
    """
    path = schema_path
    if path.startswith("/workers/"):
        path = path[len("/workers/") :]
    elif path.startswith("/workers"):
        path = path[len("/workers") :]

    segments = [s for s in path.split("/") if s]
    snake_segments = [camel_to_snake(seg) for seg in segments]
    return "__".join(snake_segments)


def build_adp_yaml_index() -> dict[str, dict[str, set[str]]]:
    """Build an index of ADP model columns from staging YAMLs.

    Returns:
        Dict mapping model_name -> {
            "columns": set of scalar column names,
            "skip_columns": set of ARRAY<STRUCT<...>> column names,
        }
    """
    index: dict[str, dict[str, set[str]]] = {}

    for directory in ADP_YAML_DIRS:
        if not directory.exists():
            continue
        for yaml_path in sorted(directory.glob("stg_adp_*.yml")):
            with yaml_path.open(encoding="utf-8") as fh:
                doc = yaml.safe_load(fh)
            if not doc:
                continue
            for model in doc.get("models", []) or []:
                model_name = model["name"]
                columns: set[str] = set()
                skip_columns: set[str] = set()
                for col in model.get("columns", []) or []:
                    data_type = str(col.get("data_type", "")).strip()
                    if data_type.startswith("ARRAY<STRUCT<"):
                        skip_columns.add(col["name"])
                    else:
                        columns.add(col["name"])
                index[model_name] = {
                    "columns": columns,
                    "skip_columns": skip_columns,
                }

    return index


def build_adp_mapping(
    pages: list[str],
    yaml_index: dict[str, dict[str, set[str]]],
) -> dict:
    """Build the ADP PDF-to-YAML mapping.

    Args:
        pages: List of text strings, one per PDF page.
        yaml_index: Model name -> {"columns": set, "skip_columns": set}.

    Returns:
        Mapping dict with entries, unmatched lists, and stats.
    """
    # Parse all entries from all pages
    all_entries: list[dict[str, str]] = []
    for page_text in pages:
        all_entries.extend(parse_adp_entries(page_text))

    # Build a flat lookup of all YAML columns across all models
    all_yaml_columns: dict[str, tuple[str, set[str]]] = {}
    for model_name, model_info in yaml_index.items():
        for col in model_info["columns"]:
            all_yaml_columns[col] = (model_name, model_info["columns"])

    # Build skip set (ARRAY<STRUCT> columns)
    skip_columns: set[str] = set()
    for model_info in yaml_index.values():
        skip_columns.update(model_info["skip_columns"])

    matched_entries: list[dict] = []
    unmatched_pdf: list[dict[str, str]] = []
    matched_yaml_cols: set[str] = set()

    for entry in all_entries:
        column_name = adp_path_to_column(entry["schema_path"])
        description = entry.get("description", "")

        if column_name in skip_columns:
            continue

        if column_name in all_yaml_columns:
            model_name = all_yaml_columns[column_name][0]
            matched_entries.append(
                {
                    "source_path": entry["schema_path"],
                    "source_field": entry["field_name"],
                    "model": model_name,
                    "column": column_name,
                    "description": description,
                    "contains_pii": classify_pii(column_name, description),
                }
            )
            matched_yaml_cols.add(column_name)
        else:
            # Check if this is a parent path (any YAML col starts with it + __)
            is_parent = any(
                yaml_col.startswith(column_name + "__") for yaml_col in all_yaml_columns
            )
            if not is_parent:
                unmatched_pdf.append(
                    {
                        "path": entry["schema_path"],
                        "field_name": entry["field_name"],
                    }
                )

    # Find unmatched YAML columns
    all_scalar_cols: set[str] = set()
    for model_info in yaml_index.values():
        all_scalar_cols.update(model_info["columns"])

    unmatched_yaml: list[dict[str, str]] = []
    for col in sorted(all_scalar_cols - matched_yaml_cols):
        for model_name, model_info in yaml_index.items():
            if col in model_info["columns"]:
                unmatched_yaml.append({"model": model_name, "column": col})
                break

    return {
        "source": "adp",
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "pdf_entries": len(all_entries),
            "yaml_columns": len(all_scalar_cols),
            "matched": len(matched_entries),
            "unmatched_pdf": len(unmatched_pdf),
            "unmatched_yaml": len(unmatched_yaml),
        },
        "entries": matched_entries,
        "unmatched_pdf": unmatched_pdf,
        "unmatched_yaml": unmatched_yaml,
    }


def _extract_adp(pdf_path: str) -> dict:
    """Extract ADP data dictionary from PDF."""
    from pypdf import PdfReader

    reader = PdfReader(pdf_path)
    pages = [page.extract_text() or "" for page in reader.pages]
    yaml_index = build_adp_yaml_index()
    return build_adp_mapping(pages, yaml_index)


def _extract_powerschool(pdf_path: str) -> dict:
    """Extract PowerSchool data dictionary from PDF."""
    from pypdf import PdfReader

    reader = PdfReader(pdf_path)
    pages = [page.extract_text() or "" for page in reader.pages]
    yaml_index = build_ps_yaml_index()
    return build_ps_mapping(pages, yaml_index)


def main() -> None:
    if len(sys.argv) != 3:
        print(
            "Usage: uv run scripts/extract_pdf_dictionary.py "
            "<pdf_path> <source_system>",
            file=sys.stderr,
        )
        sys.exit(1)

    pdf_path = sys.argv[1]
    source = sys.argv[2].lower()

    if source == "powerschool":
        result = _extract_powerschool(pdf_path)
    elif source == "adp":
        result = _extract_adp(pdf_path)
    else:
        print(f"Unknown source system: {source}", file=sys.stderr)
        sys.exit(1)

    # Write JSON output
    output_path = Path(f".claude/scratch/{source}_dictionary.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)

    # Print summary
    stats = result["stats"]
    print(f"Source: {result['source']}")
    print(f"PDF entries:    {stats['pdf_entries']}")
    print(f"YAML columns:   {stats['yaml_columns']}")
    print(f"Matched:        {stats['matched']}")
    print(f"Unmatched PDF:  {stats['unmatched_pdf']}")
    print(f"Unmatched YAML: {stats['unmatched_yaml']}")
    print(f"\nOutput written to {output_path}")

    # Show top unmatched
    if result["unmatched_pdf"][:10]:
        print("\nTop unmatched PDF entries:")
        for entry in result["unmatched_pdf"][:10]:
            if "table" in entry:
                print(f"  {entry['table']}.{entry['column']}")
            else:
                print(f"  {entry['path']} ({entry['field_name']})")
    if result["unmatched_yaml"][:10]:
        print("\nTop unmatched YAML columns:")
        for entry in result["unmatched_yaml"][:10]:
            print(f"  {entry['model']}.{entry['column']}")


if __name__ == "__main__":
    main()

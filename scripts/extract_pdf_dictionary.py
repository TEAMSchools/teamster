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

# Unicode ligatures commonly produced by PDF text extraction
_LIGATURE_MAP: dict[str, str] = {
    "\ufb00": "ff",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
}
_LIGATURE_RE = re.compile("|".join(re.escape(k) for k in _LIGATURE_MAP))


def normalize_ligatures(text: str) -> str:
    """Replace Unicode ligatures (ﬁ, ﬂ, ﬀ, etc.) with ASCII equivalents."""
    if not _LIGATURE_RE.search(text):
        return text
    return _LIGATURE_RE.sub(lambda m: _LIGATURE_MAP[m.group()], text)


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
#   "Abbreviation3.6.1 Varchar(3)A short version..."  (no spaces — pypdf artifact)
# Version: digits.digits[.digits]*
# Data type: word characters, optional parenthesized size like (10,0)
# Space between fields is optional (\s*) because pypdf sometimes drops spaces.
_PS_COLUMN_RE = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*)\s*"  # column name (space optional)
    r"(\d+\.\d+(?:\.\d+)*)\s*"  # version (space optional)
    r"([A-Za-z0-9]+(?:\([^)]*\))?)"  # data type
    r"(.+)$"  # description (rest of line, may start without space)
)

# Lines to skip
_PS_SKIP_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^Column\s*Name\s*Initial\s*Version\s*Data\s*Type\s*Description"),
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

    # Build alpha-only reverse lookup per model for fallback matching.
    # Strips non-alpha chars so "CalcMetric1" matches "calcmetric".
    _alpha_re = re.compile(r"[^a-z]")
    yaml_alpha_index: dict[str, dict[str, list[str]]] = {}
    for model_name, cols in yaml_index.items():
        alpha_map: dict[str, list[str]] = {}
        for col in cols:
            norm = _alpha_re.sub("", col.lower())
            alpha_map.setdefault(norm, []).append(col)
        yaml_alpha_index[model_name] = alpha_map

    for table_name, col_entries in table_columns.items():
        model_name = ps_table_to_model_name(table_name)
        yaml_columns = yaml_index.get(model_name, set())
        alpha_map = yaml_alpha_index.get(model_name, {})

        for entry in col_entries:
            pdf_col = entry["source_column"]
            snake_col = pascal_to_snake(pdf_col)
            lower_col = pdf_col.lower()
            alpha_col = _alpha_re.sub("", pdf_col.lower())
            description = entry.get("description", "")

            # Try snake_case first, then raw lowercase, then alpha-only
            # normalization (catches trailing digits like "Config1" → "config")
            matched_col = None
            if snake_col in yaml_columns:
                matched_col = snake_col
            elif lower_col in yaml_columns:
                matched_col = lower_col
            elif alpha_col in alpha_map:
                candidates = alpha_map[alpha_col]
                if len(candidates) == 1:
                    matched_col = candidates[0]

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

    # Conformed columns: appear across many PS tables with identical meaning.
    # Match any unmatched YAML column that fits these patterns.
    _CONFORMED_COLUMNS: dict[str, tuple[str, bool]] = {
        # (description, contains_pii)
        # Audit columns (Dagster-injected)
        "executionid": ("Dagster run execution identifier.", False),
        "ip_address": ("IP address of the client that made the change.", True),
        "transaction_date": ("Timestamp of the database transaction.", False),
        "whomodifiedid": (
            "Identifier of the user who last modified the record.",
            False,
        ),
        "whomodifiedtype": ("Type of user who last modified the record.", False),
        # PS system audit columns
        "whencreated": ("Timestamp when the record was created.", False),
        "whenmodified": ("Timestamp when the record was last modified.", False),
        "whocreated": ("Username of the account that created the record.", False),
        "whomodified": (
            "Username of the account that last modified the record.",
            False,
        ),
        # PS system identifiers
        "psguid": ("PowerSchool globally unique identifier for the record.", False),
        "student_number": (
            "District-assigned student number, unique within the district.",
            True,
        ),
    }
    # Suffix patterns: any column ending with "dcid" is a PS internal identifier
    _CONFORMED_SUFFIXES: dict[str, tuple[str, bool]] = {
        "dcid": ("PowerSchool internal database record identifier (DCID).", False),
    }

    for model_name, yaml_cols in yaml_index.items():
        matched_cols = all_matched_yaml_columns.get(model_name, set())
        for col in yaml_cols - matched_cols:
            desc_pii = _CONFORMED_COLUMNS.get(col)
            if desc_pii is None:
                for suffix, dp in _CONFORMED_SUFFIXES.items():
                    if col.endswith(suffix):
                        desc_pii = dp
                        break
            if desc_pii is not None:
                description, is_pii = desc_pii
                matched_entries.append(
                    {
                        "source_table": "(conformed)",
                        "source_column": col,
                        "model": model_name,
                        "column": col,
                        "description": description,
                        "contains_pii": is_pii,
                    }
                )
                all_matched_yaml_columns.setdefault(model_name, set()).add(col)

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


def _rejoin_adp_lines(page_text: str) -> list[str]:
    """Rejoin ADP entry lines split by PDF text extraction.

    pypdf sometimes splits camelCase path segments across lines, e.g.:
        /workers/person/raceCode/identificationMethodCode/short
        Name Short Name Y
    This joins such continuations into single lines.
    """
    raw_lines = page_text.split("\n")
    joined: list[str] = []
    pending: str | None = None

    for raw in raw_lines:
        line = raw.strip()
        if not line:
            continue
        if pending is not None:
            line = pending + " " + line
            pending = None
        # Incomplete path entry: starts with /workers/ but no Y/NA terminator
        if line.startswith("/workers/") and not _ADP_ENTRY_RE.match(line):
            pending = line
        else:
            joined.append(line)

    if pending:
        joined.append(pending)
    return joined


def _rejoin_camel_segment(schema_path: str, middle_text: str) -> tuple[str, str]:
    """Fix split camelCase in ADP paths.

    pypdf can insert a space inside camelCase: /workers/.../short Name ...
    The regex captures path="/workers/.../short", middle="Name Short Name".
    Detect this by checking if the last path segment is all-lowercase (fragment)
    and the middle starts with an uppercase word (the continuation).
    """
    last_segment = schema_path.rsplit("/", 1)[-1]
    if last_segment != last_segment.lower():
        return schema_path, middle_text
    if not middle_text or not middle_text[0].isupper():
        return schema_path, middle_text

    parts = middle_text.split(None, 1)
    suffix = parts[0]
    if suffix.isalpha():
        schema_path = schema_path + suffix
        middle_text = parts[1].strip() if len(parts) > 1 else ""
    return schema_path, middle_text


def parse_adp_entries(page_text: str) -> list[dict[str, str]]:
    """Parse ADP data dictionary entries from PDF page text.

    Returns a list of dicts with keys: schema_path, field_name, description.
    The description includes the field name and any note text.
    """
    entries: list[dict[str, str]] = []

    for line in _rejoin_adp_lines(page_text):
        match = _ADP_ENTRY_RE.match(line)
        if not match:
            continue

        schema_path = match.group(1)
        middle_text = match.group(2).strip()

        # Fix split camelCase segments (e.g., /short + Name → /shortName)
        schema_path, middle_text = _rejoin_camel_segment(schema_path, middle_text)

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
        schema_path = entry["schema_path"]
        description = entry.get("description", "")
        column_name = adp_path_to_column(schema_path)

        if column_name in skip_columns:
            continue

        # Progressive word-join: if the path doesn't match, try absorbing
        # words from the description into the path.  pypdf splits path
        # segments at arbitrary points (e.g., "codeValue" → "co deValue",
        # "shortName" → "short Name"), so we progressively rejoin up to 3
        # words from the description until we find a YAML match.
        if column_name not in all_yaml_columns and description:
            words = description.split()
            for i in range(1, min(4, len(words) + 1)):
                candidate_path = schema_path + "".join(words[:i])
                candidate_col = adp_path_to_column(candidate_path)
                if candidate_col in all_yaml_columns or candidate_col in skip_columns:
                    schema_path = candidate_path
                    column_name = candidate_col
                    description = " ".join(words[i:])
                    break

        if column_name in skip_columns:
            continue

        if column_name in all_yaml_columns:
            model_name = all_yaml_columns[column_name][0]
            matched_entries.append(
                {
                    "source_path": schema_path,
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
                        "path": schema_path,
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
    pages = [normalize_ligatures(page.extract_text() or "") for page in reader.pages]
    yaml_index = build_adp_yaml_index()
    return build_adp_mapping(pages, yaml_index)


def _extract_powerschool(pdf_path: str) -> dict:
    """Extract PowerSchool data dictionary from PDF."""
    from pypdf import PdfReader

    reader = PdfReader(pdf_path)
    pages = [normalize_ligatures(page.extract_text() or "") for page in reader.pages]
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

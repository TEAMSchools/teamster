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

import re


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
    re.compile(r"(^|__)lastfirst($|_)", re.IGNORECASE),
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
            entries.append(
                {
                    "source_column": match.group(1),
                    "description": match.group(4).strip(),
                }
            )

    return entries


def main() -> None:
    raise NotImplementedError


if __name__ == "__main__":
    main()

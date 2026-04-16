# Data Dictionary Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build two PEP 723 scripts that extract column descriptions and PII
flags from PowerSchool and ADP data dictionary PDFs, then write them into dbt
staging YAML properties files.

**Architecture:** Script 1 (`extract_pdf_dictionary.py`) reads a source-system
PDF, parses table/column entries via `pypdf` + regex, matches them to staging
YAML column names, and outputs a JSON mapping to `.claude/scratch/`. Script 2
(`enrich_staging_descriptions.py`) reads one or more JSON mappings and writes
`description:` and `config.meta.contains_pii:` into staging YAML files using
`pyyaml`. Both scripts share case-conversion and PII-classification helpers
tested via a shared test file.

**Tech Stack:** Python 3.13, `uv run`, `pypdf>=4.0`, `pyyaml>=6.0`, `pytest`.

**Design reference:**
[2026-04-16-data-dictionary-enrichment-design.md](../specs/2026-04-16-data-dictionary-enrichment-design.md)

---

## File Structure

| File                                        | Responsibility                                        |
| ------------------------------------------- | ----------------------------------------------------- |
| `scripts/extract_pdf_dictionary.py`         | CREATE -- Script 1: PDF parsing + JSON mapping output |
| `scripts/enrich_staging_descriptions.py`    | CREATE -- Script 2: JSON mapping to YAML enrichment   |
| `tests/test_extract_pdf_dictionary.py`      | CREATE -- pytest unit tests for Script 1 helpers      |
| `tests/test_enrich_staging_descriptions.py` | CREATE -- pytest unit tests for Script 2 helpers      |
| `scripts/CLAUDE.md`                         | MODIFY -- add both scripts to the catalog table       |

---

## Conventions Used In This Plan

- All paths are relative to the worktree root
  `/workspaces/teamster/.worktrees/cbini/feat/claude-data-dictionary-enrichment`.
- All shell commands are run from the worktree root unless noted.
- Python runs via `uv run` -- never bare `python`.
- All commits use conventional commits (`feat(scripts): ...`, `test: ...`,
  `docs: ...`), referencing `#3516`.
- Stage changes with `git add <explicit paths>` in this plan -- subagents must
  name specific files per the project CLAUDE.md.
- `trunk fmt` is handled by the PostToolUse hook -- do not run manually.
- If `git commit -m` is blocked by the hook, write the message to
  `.claude/scratch/commit-msg.txt` and use `git commit -F`.

---

## Task 1: Scaffold both scripts and test files

**Files:**

- Create: `scripts/extract_pdf_dictionary.py`
- Create: `scripts/enrich_staging_descriptions.py`
- Create: `tests/test_extract_pdf_dictionary.py`
- Create: `tests/test_enrich_staging_descriptions.py`

- [ ] **Step 1: Write the minimal Script 1 skeleton with PEP 723 header**

Write to `scripts/extract_pdf_dictionary.py`:

```python
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


def main() -> None:
    raise NotImplementedError


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write the minimal Script 2 skeleton with PEP 723 header**

Write to `scripts/enrich_staging_descriptions.py`:

```python
# /// script
# requires-python = ">=3.13"
# dependencies = ["pyyaml>=6.0"]
# ///

"""Enrich dbt staging YAML files with descriptions and PII flags.

Reads JSON mapping file(s) produced by extract_pdf_dictionary.py and writes
description and config.meta.contains_pii to staging YAML properties files.

Usage:
    uv run scripts/enrich_staging_descriptions.py <json_path> [<json_path> ...]

Design reference:
    docs/superpowers/specs/2026-04-16-data-dictionary-enrichment-design.md
"""

from __future__ import annotations


def main() -> None:
    raise NotImplementedError


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Write the test harness for Script 1**

Write to `tests/test_extract_pdf_dictionary.py`:

```python
"""Unit tests for scripts/extract_pdf_dictionary.py.

The script filename uses underscores specifically so we can import it.
We use importlib.util rather than changing project-wide pytest config,
keeping the import pattern local to this test file.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO_ROOT / "scripts" / "extract_pdf_dictionary.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "extract_pdf_dictionary", _SCRIPT
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_script_module_loads() -> None:
    module = _load_script()
    assert callable(module.main)
```

- [ ] **Step 4: Write the test harness for Script 2**

Write to `tests/test_enrich_staging_descriptions.py`:

```python
"""Unit tests for scripts/enrich_staging_descriptions.py.

The script filename uses underscores specifically so we can import it.
We use importlib.util rather than changing project-wide pytest config,
keeping the import pattern local to this test file.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO_ROOT / "scripts" / "enrich_staging_descriptions.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "enrich_staging_descriptions", _SCRIPT
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_script_module_loads() -> None:
    module = _load_script()
    assert callable(module.main)
```

- [ ] **Step 5: Run the smoke tests and verify they pass**

```bash
uv run pytest tests/test_extract_pdf_dictionary.py tests/test_enrich_staging_descriptions.py -v
```

Expected: both `test_script_module_loads` tests PASSED.

- [ ] **Step 6: Commit**

```bash
git add scripts/extract_pdf_dictionary.py \
        scripts/enrich_staging_descriptions.py \
        tests/test_extract_pdf_dictionary.py \
        tests/test_enrich_staging_descriptions.py
git commit -m "feat(scripts): scaffold data dictionary enrichment scripts

Empty skeletons with PEP 723 headers and importable test harnesses
for both extract and enrich scripts.
Tracked on #3516."
```

---

## Task 2: Case conversion helpers -- full TDD

**Purpose:** Convert PascalCase column names (PowerSchool) and camelCase path
segments (ADP) to snake_case. These are the foundation of the matching logic.

**Files:**

- Modify: `scripts/extract_pdf_dictionary.py`
- Modify: `tests/test_extract_pdf_dictionary.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_extract_pdf_dictionary.py`:

```python
import pytest


class TestPascalToSnake:
    def test_simple(self) -> None:
        module = _load_script()
        assert module.pascal_to_snake("StudentNumber") == "student_number"

    def test_all_caps_short(self) -> None:
        module = _load_script()
        assert module.pascal_to_snake("ID") == "id"

    def test_mixed_caps_and_pascal(self) -> None:
        module = _load_script()
        assert module.pascal_to_snake("DCid") == "dcid"

    def test_consecutive_caps(self) -> None:
        module = _load_script()
        assert module.pascal_to_snake("SSN") == "ssn"

    def test_single_word(self) -> None:
        module = _load_script()
        assert module.pascal_to_snake("Gender") == "gender"

    def test_already_lowercase(self) -> None:
        module = _load_script()
        assert module.pascal_to_snake("schoolid") == "schoolid"

    def test_underscore_preserved(self) -> None:
        module = _load_script()
        assert module.pascal_to_snake("Alert_Discipline") == "alert_discipline"

    def test_trailing_caps(self) -> None:
        module = _load_script()
        assert module.pascal_to_snake("StudentID") == "student_id"

    def test_complex_mixed(self) -> None:
        module = _load_script()
        assert module.pascal_to_snake("GPAPoints") == "gpa_points"

    def test_s_nj_prefix(self) -> None:
        """Extension table names like S_NJ_STU_X stay lowercase."""
        module = _load_script()
        assert module.pascal_to_snake("s_nj_stu_x") == "s_nj_stu_x"


class TestCamelToSnake:
    def test_simple(self) -> None:
        module = _load_script()
        assert module.camel_to_snake("birthDate") == "birth_date"

    def test_single_word(self) -> None:
        module = _load_script()
        assert module.camel_to_snake("person") == "person"

    def test_multi_segment(self) -> None:
        module = _load_script()
        assert module.camel_to_snake("genderCode") == "gender_code"

    def test_consecutive_upper(self) -> None:
        module = _load_script()
        assert module.camel_to_snake("emailURI") == "email_uri"

    def test_already_snake(self) -> None:
        module = _load_script()
        assert module.camel_to_snake("birth_date") == "birth_date"

    def test_code_value(self) -> None:
        module = _load_script()
        assert module.camel_to_snake("codeValue") == "code_value"

    def test_long_camel(self) -> None:
        module = _load_script()
        assert (
            module.camel_to_snake("countrySubdivisionLevel1")
            == "country_subdivision_level_1"
        )

    def test_formatted_name(self) -> None:
        module = _load_script()
        assert module.camel_to_snake("formattedName") == "formatted_name"
```

- [ ] **Step 2: Run tests; verify they fail**

```bash
uv run pytest tests/test_extract_pdf_dictionary.py -v -k "PascalToSnake or CamelToSnake"
```

Expected: all tests fail with `AttributeError`.

- [ ] **Step 3: Implement `pascal_to_snake` and `camel_to_snake`**

Add to `scripts/extract_pdf_dictionary.py` above `main()`:

```python
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
        # Insert underscore before transitions:
        # 1. Uppercase followed by lowercase: "ID" + "a" -> "ID_a"
        # 2. Lowercase/digit followed by uppercase: "student" + "N" -> "student_N"
        s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", part)
        s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
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
```

- [ ] **Step 4: Run tests; verify they pass**

```bash
uv run pytest tests/test_extract_pdf_dictionary.py -v -k "PascalToSnake or CamelToSnake"
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/extract_pdf_dictionary.py \
        tests/test_extract_pdf_dictionary.py
git commit -m "feat(scripts): add pascal_to_snake and camel_to_snake helpers

Case conversion functions for matching PDF column names to staging YAML
column names. PascalCase for PowerSchool, camelCase for ADP.
Tracked on #3516."
```

---

## Task 3: PII heuristic classifier -- full TDD

**Purpose:** Classify columns as PII based on column name patterns and
description keywords. Defaults to `false`; flags `true` for
names/DOB/SSN/address/phone/email/government IDs.

**Files:**

- Modify: `scripts/extract_pdf_dictionary.py`
- Modify: `tests/test_extract_pdf_dictionary.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_extract_pdf_dictionary.py`:

```python
class TestClassifyPii:
    """Test the PII heuristic classifier."""

    def test_name_columns_are_pii(self) -> None:
        module = _load_script()
        assert module.classify_pii("first_name", "") is True
        assert module.classify_pii("last_name", "") is True
        assert module.classify_pii("middle_name", "") is True
        assert module.classify_pii("formatted_name", "") is True
        assert module.classify_pii("family_name_1", "") is True
        assert module.classify_pii("given_name", "") is True
        assert module.classify_pii("nick_name", "") is True
        assert module.classify_pii("lastfirst", "") is True

    def test_dob_is_pii(self) -> None:
        module = _load_script()
        assert module.classify_pii("dob", "") is True
        assert module.classify_pii("birth_date", "") is True
        assert module.classify_pii("person__birth_date", "") is True

    def test_ssn_is_pii(self) -> None:
        module = _load_script()
        assert module.classify_pii("ssn", "") is True
        assert module.classify_pii("social_security", "") is True

    def test_address_is_pii(self) -> None:
        module = _load_script()
        assert module.classify_pii("street", "") is True
        assert module.classify_pii("city", "") is True
        assert module.classify_pii("zip", "") is True
        assert module.classify_pii("postal_code", "") is True
        assert module.classify_pii("line_one", "Legal address line one.") is True
        assert module.classify_pii("city_name", "") is True

    def test_phone_is_pii(self) -> None:
        module = _load_script()
        assert module.classify_pii("home_phone", "") is True
        assert module.classify_pii("dial_number", "") is True
        assert module.classify_pii("guardianfax", "") is True

    def test_email_is_pii(self) -> None:
        module = _load_script()
        assert module.classify_pii("guardianemail", "") is True
        assert module.classify_pii("email_uri", "") is True

    def test_description_keyword_triggers_pii(self) -> None:
        module = _load_script()
        assert module.classify_pii("some_field", "Social Security Number") is True
        assert (
            module.classify_pii("some_field", "Date of birth for the student")
            is True
        )
        assert (
            module.classify_pii("some_field", "Home address of the worker")
            is True
        )
        assert (
            module.classify_pii("some_field", "Emergency contact phone number")
            is True
        )

    def test_non_pii_columns(self) -> None:
        module = _load_script()
        assert module.classify_pii("schoolid", "") is False
        assert module.classify_pii("grade_level", "") is False
        assert module.classify_pii("entrydate", "") is False
        assert module.classify_pii("termid", "") is False
        assert module.classify_pii("code_value", "") is False
        assert module.classify_pii("effective_date", "") is False

    def test_government_id_is_pii(self) -> None:
        module = _load_script()
        assert module.classify_pii("state_studentnumber", "") is True
        assert module.classify_pii("web_password", "") is True

    def test_emergency_contact_is_pii(self) -> None:
        module = _load_script()
        assert (
            module.classify_pii(
                "emerg_contact_1", "Emergency contact information."
            )
            is True
        )
```

- [ ] **Step 2: Run tests; verify they fail**

```bash
uv run pytest tests/test_extract_pdf_dictionary.py -v -k "ClassifyPii"
```

Expected: all tests fail with `AttributeError`.

- [ ] **Step 3: Implement `classify_pii`**

Add to `scripts/extract_pdf_dictionary.py` below the case conversion helpers:

```python
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
```

- [ ] **Step 4: Run tests; verify they pass**

```bash
uv run pytest tests/test_extract_pdf_dictionary.py -v -k "ClassifyPii"
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/extract_pdf_dictionary.py \
        tests/test_extract_pdf_dictionary.py
git commit -m "feat(scripts): add PII heuristic classifier

Pattern-based classification on column name and description keywords.
Defaults false, flags true for names/DOB/SSN/address/phone/email/
government IDs/emergency contacts.
Tracked on #3516."
```

---

## Task 4: PowerSchool PDF table-boundary detector

**Purpose:** Parse raw `pypdf` text output to identify where table sections
begin and end. Each table has a header like `Students, 167 (ver3.6.1)` or
`CC (ver3.6.1)` and a column listing below it. The header may appear at the
bottom of a page (as a footer) or at the top. The detector extracts
`(table_name, column_rows_text)` pairs.

**Files:**

- Modify: `scripts/extract_pdf_dictionary.py`
- Modify: `tests/test_extract_pdf_dictionary.py`

- [ ] **Step 1: Write the failing tests with fixture text**

Append to `tests/test_extract_pdf_dictionary.py`:

```python
# Representative text blocks extracted from real PowerSchool PDF pages.
# These are minimal fixtures -- not full pages.

PS_FIXTURE_PAGE_WITH_HEADER = """\
736
This table maintains Student demographics and other School related information such as Lunch ID, Grade Level and scheduling data.
Column Name InitialVersion Data Type Description
Alert_Discipline 3.6.1 CLOB One of many various alerts in PowerSchool. This field stores the text tied to the alert.
Alert_DisciplineExpires 3.6.1 Date An expiration date for the Discipline alert.
StudentNumber 3.6.1 Number(10,0) The student's assigned number.
Students, 167 (ver3.6.1)
PowerSchool Private Information – Confidential
"""

PS_FIXTURE_PAGE_CONTINUATION = """\
737
SSN 3.6.1 Varchar2(12) Social security number. Masked by default.
FedEthnicity 5.0.3 Number(10,0) Federal ethnicity code.
Mailing_Street 3.6.1 Varchar2(70) Mailing street address.
Students, 167 (ver3.6.1)
PowerSchool Private Information – Confidential
"""

PS_FIXTURE_NEW_TABLE = """\
800
This table contains CC (Current Class) data.
Column Name InitialVersion Data Type Description
StudentID 3.6.1 Number(10,0) Links to students table.
SectionID 3.6.1 Number(10,0) Links to sections table.
DateEnrolled 3.6.1 Date Date enrolled into section.
CC (ver3.6.1)
"""

PS_FIXTURE_TABLE_WITH_COUNT = """\
50
AssignmentSectionID 3.6.1 Number(10,0) Related assignment section.
Points 3.6.1 Number(10,0) Points earned.
AssignmentScore, 2 (ver3.6.1)
PowerSchool Private Information – Confidential
"""


class TestPsTableNameExtractor:
    """Test extracting the table name from a page's footer-style header."""

    def test_extracts_table_with_count(self) -> None:
        module = _load_script()
        result = module.extract_ps_table_name(PS_FIXTURE_PAGE_WITH_HEADER)
        assert result == "Students"

    def test_extracts_table_without_count(self) -> None:
        module = _load_script()
        result = module.extract_ps_table_name(PS_FIXTURE_NEW_TABLE)
        assert result == "CC"

    def test_extracts_table_from_score_page(self) -> None:
        module = _load_script()
        result = module.extract_ps_table_name(PS_FIXTURE_TABLE_WITH_COUNT)
        assert result == "AssignmentScore"

    def test_returns_none_for_no_header(self) -> None:
        module = _load_script()
        result = module.extract_ps_table_name("Some random text\nwithout headers\n")
        assert result is None
```

- [ ] **Step 2: Run tests; verify they fail**

```bash
uv run pytest tests/test_extract_pdf_dictionary.py -v -k "PsTableNameExtractor"
```

Expected: all fail with `AttributeError`.

- [ ] **Step 3: Implement `extract_ps_table_name`**

Add to `scripts/extract_pdf_dictionary.py`:

```python
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
```

- [ ] **Step 4: Run tests; verify they pass**

```bash
uv run pytest tests/test_extract_pdf_dictionary.py -v -k "PsTableNameExtractor"
```

Expected: all four pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/extract_pdf_dictionary.py \
        tests/test_extract_pdf_dictionary.py
git commit -m "feat(scripts): add PowerSchool table name extractor

Regex-based extraction of table names from PDF page footer headers.
Handles 'TableName, N (verX.Y.Z)' and 'TableName (verX.Y.Z)' formats.
Tracked on #3516."
```

---

## Task 5: PowerSchool column entry parser

**Purpose:** Parse individual column lines from the extracted PDF text. Each
column entry looks like `ColumnName VersionNumber DataType Description...`.
Multi-line descriptions are joined to the preceding column.

**Files:**

- Modify: `scripts/extract_pdf_dictionary.py`
- Modify: `tests/test_extract_pdf_dictionary.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_extract_pdf_dictionary.py`:

```python
class TestPsColumnParser:
    """Test parsing individual column lines from PS PDF text."""

    def test_parses_simple_column(self) -> None:
        module = _load_script()
        text = "StudentNumber 3.6.1 Number(10,0) The student's assigned number."
        entries = module.parse_ps_columns(text)
        assert len(entries) == 1
        assert entries[0]["source_column"] == "StudentNumber"
        assert entries[0]["description"] == "The student's assigned number."

    def test_parses_multiple_columns(self) -> None:
        module = _load_script()
        text = (
            "Alert_Discipline 3.6.1 CLOB "
            "One of many various alerts in PowerSchool. "
            "This field stores the text tied to the alert.\n"
            "StudentNumber 3.6.1 Number(10,0) "
            "The student's assigned number.\n"
        )
        entries = module.parse_ps_columns(text)
        assert len(entries) == 2
        assert entries[0]["source_column"] == "Alert_Discipline"
        assert entries[1]["source_column"] == "StudentNumber"

    def test_skips_header_line(self) -> None:
        module = _load_script()
        text = (
            "Column Name InitialVersion Data Type Description\n"
            "StudentNumber 3.6.1 Number(10,0) The student's assigned number."
        )
        entries = module.parse_ps_columns(text)
        assert len(entries) == 1
        assert entries[0]["source_column"] == "StudentNumber"

    def test_skips_page_number_and_footer(self) -> None:
        module = _load_script()
        text = (
            "736\n"
            "StudentNumber 3.6.1 Number(10,0) The student's assigned number.\n"
            "Students, 167 (ver3.6.1)\n"
            "PowerSchool Private Information \u2013 Confidential\n"
        )
        entries = module.parse_ps_columns(text)
        assert len(entries) == 1
        assert entries[0]["source_column"] == "StudentNumber"

    def test_various_data_types(self) -> None:
        module = _load_script()
        text = (
            "Alert_Discipline 3.6.1 CLOB Alert text.\n"
            "FedEthnicity 5.0.3 Number(10,0) Federal ethnicity.\n"
            "SSN 3.6.1 Varchar2(12) Social security number.\n"
            "DOB 3.6.1 Date Date of birth.\n"
        )
        entries = module.parse_ps_columns(text)
        assert len(entries) == 4
        assert entries[0]["source_column"] == "Alert_Discipline"
        assert entries[2]["source_column"] == "SSN"

    def test_clob_description_extracted(self) -> None:
        module = _load_script()
        text = "Alert_Discipline 3.6.1 CLOB One of many various alerts."
        entries = module.parse_ps_columns(text)
        assert entries[0]["description"] == "One of many various alerts."
```

- [ ] **Step 2: Run tests; verify they fail**

```bash
uv run pytest tests/test_extract_pdf_dictionary.py -v -k "PsColumnParser"
```

Expected: all fail with `AttributeError`.

- [ ] **Step 3: Implement `parse_ps_columns`**

Add to `scripts/extract_pdf_dictionary.py`:

```python
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
```

- [ ] **Step 4: Run tests; verify they pass**

```bash
uv run pytest tests/test_extract_pdf_dictionary.py -v -k "PsColumnParser"
```

Expected: all six pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/extract_pdf_dictionary.py \
        tests/test_extract_pdf_dictionary.py
git commit -m "feat(scripts): add PowerSchool column entry parser

Regex-based parser for column lines in PS PDF text. Handles various data
types (CLOB, Number, Varchar2, Date) and skips headers/footers/page nums.
Tracked on #3516."
```

---

## Task 6: PowerSchool YAML column matcher

**Purpose:** Match parsed PDF entries to actual staging YAML column names. Given
a PDF table name like `Students`, find `stg_powerschool__students.yml` in the
known paths and build a column-name lookup set. Convert PDF column names via
`pascal_to_snake` for matching.

**Files:**

- Modify: `scripts/extract_pdf_dictionary.py`
- Modify: `tests/test_extract_pdf_dictionary.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_extract_pdf_dictionary.py`:

```python
class TestPsTableToModelName:
    """Test converting PDF table names to dbt model names."""

    def test_simple_table(self) -> None:
        module = _load_script()
        assert (
            module.ps_table_to_model_name("Students")
            == "stg_powerschool__students"
        )

    def test_mixed_case(self) -> None:
        module = _load_script()
        assert (
            module.ps_table_to_model_name("StoredGrades")
            == "stg_powerschool__storedgrades"
        )

    def test_short_name(self) -> None:
        module = _load_script()
        assert module.ps_table_to_model_name("CC") == "stg_powerschool__cc"

    def test_extension_table(self) -> None:
        module = _load_script()
        assert (
            module.ps_table_to_model_name("S_NJ_STU_X")
            == "stg_powerschool__s_nj_stu_x"
        )

    def test_camel_compound(self) -> None:
        module = _load_script()
        assert (
            module.ps_table_to_model_name("AssignmentScore")
            == "stg_powerschool__assignmentscore"
        )

    def test_person_table(self) -> None:
        module = _load_script()
        assert (
            module.ps_table_to_model_name("Person")
            == "stg_powerschool__person"
        )


class TestBuildPsYamlIndex:
    """Test building the YAML column lookup index."""

    def test_index_contains_students_columns(self) -> None:
        module = _load_script()
        index = module.build_ps_yaml_index()
        # stg_powerschool__students.yml exists and has columns
        assert "stg_powerschool__students" in index
        columns = index["stg_powerschool__students"]
        assert "first_name" in columns
        assert "student_number" not in columns or "id" in columns
        # Verify it's a set
        assert isinstance(columns, set)

    def test_index_contains_cc_columns(self) -> None:
        module = _load_script()
        index = module.build_ps_yaml_index()
        assert "stg_powerschool__cc" in index
        columns = index["stg_powerschool__cc"]
        assert "studentid" in columns or "dcid" in columns
```

- [ ] **Step 2: Run tests; verify they fail**

```bash
uv run pytest tests/test_extract_pdf_dictionary.py -v -k "PsTableToModelName or BuildPsYamlIndex"
```

Expected: all fail with `AttributeError`.

- [ ] **Step 3: Implement `ps_table_to_model_name` and `build_ps_yaml_index`**

Add to `scripts/extract_pdf_dictionary.py`:

```python
from pathlib import Path

import yaml

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
                }
                if model_name in index:
                    index[model_name].update(columns)
                else:
                    index[model_name] = columns

    return index
```

- [ ] **Step 4: Run tests; verify they pass**

```bash
uv run pytest tests/test_extract_pdf_dictionary.py -v -k "PsTableToModelName or BuildPsYamlIndex"
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/extract_pdf_dictionary.py \
        tests/test_extract_pdf_dictionary.py
git commit -m "feat(scripts): add PS table-to-model name converter and YAML index

Converts PDF table names to staging model names and builds a column name
lookup index from all PowerSchool staging YAML files.
Tracked on #3516."
```

---

## Task 7: Script 1 PowerSchool orchestration + JSON output

**Purpose:** Wire up the full extraction pipeline for PowerSchool: read PDF
page-by-page, parse tables and columns, match against YAML index, classify PII,
and output the JSON mapping file.

**Files:**

- Modify: `scripts/extract_pdf_dictionary.py`
- Modify: `tests/test_extract_pdf_dictionary.py`

- [ ] **Step 1: Write the test for JSON output structure**

Append to `tests/test_extract_pdf_dictionary.py`:

```python
import json


class TestBuildPsMapping:
    """Test the PowerSchool PDF-to-JSON mapping builder."""

    def test_mapping_structure_from_fixture_pages(self) -> None:
        module = _load_script()
        # Simulate extracted pages
        pages = [PS_FIXTURE_PAGE_WITH_HEADER, PS_FIXTURE_PAGE_CONTINUATION]
        yaml_index = {
            "stg_powerschool__students": {
                "alert_discipline",
                "alert_disciplineexpires",
                "student_number",
                "ssn",
                "fedethnicity",
                "mailing_street",
            },
        }
        result = module.build_ps_mapping(pages, yaml_index)

        assert result["source"] == "powerschool"
        assert "extracted_at" in result
        assert "stats" in result
        assert "entries" in result
        assert "unmatched_pdf" in result
        assert "unmatched_yaml" in result

        # Check that matched entries exist
        matched_cols = {e["column"] for e in result["entries"]}
        assert "student_number" in matched_cols
        assert "alert_discipline" in matched_cols

    def test_pii_classification_in_mapping(self) -> None:
        module = _load_script()
        pages = [PS_FIXTURE_PAGE_WITH_HEADER, PS_FIXTURE_PAGE_CONTINUATION]
        yaml_index = {
            "stg_powerschool__students": {
                "alert_discipline",
                "student_number",
                "ssn",
                "mailing_street",
            },
        }
        result = module.build_ps_mapping(pages, yaml_index)

        entries_by_col = {e["column"]: e for e in result["entries"]}
        # SSN should be PII
        if "ssn" in entries_by_col:
            assert entries_by_col["ssn"]["contains_pii"] is True
        # alert_discipline should not be PII
        if "alert_discipline" in entries_by_col:
            assert entries_by_col["alert_discipline"]["contains_pii"] is False
        # mailing_street should be PII
        if "mailing_street" in entries_by_col:
            assert entries_by_col["mailing_street"]["contains_pii"] is True

    def test_stats_counts(self) -> None:
        module = _load_script()
        pages = [PS_FIXTURE_PAGE_WITH_HEADER]
        yaml_index = {
            "stg_powerschool__students": {
                "alert_discipline",
                "student_number",
            },
        }
        result = module.build_ps_mapping(pages, yaml_index)
        stats = result["stats"]
        assert stats["matched"] > 0
        assert isinstance(stats["pdf_entries"], int)
        assert isinstance(stats["unmatched_pdf"], int)
```

- [ ] **Step 2: Run tests; verify they fail**

```bash
uv run pytest tests/test_extract_pdf_dictionary.py -v -k "BuildPsMapping"
```

Expected: all fail with `AttributeError`.

- [ ] **Step 3: Implement `build_ps_mapping`**

Add to `scripts/extract_pdf_dictionary.py`:

```python
import json
import sys
from datetime import datetime, timezone


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
    # Collect all (table_name, column_entries) from pages
    table_columns: dict[str, list[dict[str, str]]] = {}

    for page_text in pages:
        table_name = extract_ps_table_name(page_text)
        if table_name is None:
            continue

        entries = parse_ps_columns(page_text)
        if table_name not in table_columns:
            table_columns[table_name] = []
        table_columns[table_name].extend(entries)

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
            description = entry.get("description", "")

            if snake_col in yaml_columns:
                matched_entries.append(
                    {
                        "source_table": table_name,
                        "source_column": pdf_col,
                        "model": model_name,
                        "column": snake_col,
                        "description": description,
                        "contains_pii": classify_pii(snake_col, description),
                    }
                )
                if model_name not in all_matched_yaml_columns:
                    all_matched_yaml_columns[model_name] = set()
                all_matched_yaml_columns[model_name].add(snake_col)
            else:
                unmatched_pdf.append(
                    {"table": table_name, "column": pdf_col}
                )

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
        "entries": matched_entries,
        "unmatched_pdf": unmatched_pdf,
        "unmatched_yaml": unmatched_yaml,
    }
```

- [ ] **Step 4: Run tests; verify they pass**

```bash
uv run pytest tests/test_extract_pdf_dictionary.py -v -k "BuildPsMapping"
```

Expected: all three pass.

- [ ] **Step 5: Implement the PowerSchool branch of `main()`**

Replace the `main()` stub in `scripts/extract_pdf_dictionary.py`:

```python
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
            print(f"  {entry['table']}.{entry['column']}")
    if result["unmatched_yaml"][:10]:
        print("\nTop unmatched YAML columns:")
        for entry in result["unmatched_yaml"][:10]:
            print(f"  {entry['model']}.{entry['column']}")
```

Note: `_extract_adp` will be implemented in Task 10. Add a placeholder:

```python
def _extract_adp(pdf_path: str) -> dict:
    """Extract ADP data dictionary from PDF."""
    raise NotImplementedError("ADP extraction not yet implemented")
```

- [ ] **Step 6: Run all tests**

```bash
uv run pytest tests/test_extract_pdf_dictionary.py -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add scripts/extract_pdf_dictionary.py \
        tests/test_extract_pdf_dictionary.py
git commit -m "feat(scripts): add PS mapping builder and main() orchestration

Wires up full PowerSchool extraction pipeline: PDF pages -> table/column
parsing -> YAML matching -> PII classification -> JSON output.
Tracked on #3516."
```

---

## Task 8: ADP PDF path parser

**Purpose:** Extract schema-location/field-name pairs from the ADP PDF appendix.
Each line has a JSON path starting with `/workers/`, a field name label, an
optional note, and a `Y`/`NA` flag.

**Files:**

- Modify: `scripts/extract_pdf_dictionary.py`
- Modify: `tests/test_extract_pdf_dictionary.py`

- [ ] **Step 1: Write the failing tests with fixture text**

Append to `tests/test_extract_pdf_dictionary.py`:

```python
# Representative text blocks extracted from real ADP PDF pages.

ADP_FIXTURE_PAGE = """\
/workers/person/birthDate Birth Date Masked by default. Y
/workers/person/raceCode Race Y
/workers/person/genderCode Gender Y
/workers/person/communication/emails/emailUri Personal Email Y
/workers/person/legalAddress/postalCode Postal Code Y
/workers/workerDates/originalHireDate Original Hire Date Y
/workers/workerDates/terminationDate Termination Date Y
"""

ADP_FIXTURE_PAGE_2 = """\
/workers/person/legalName/givenName Legal First Name Y
/workers/person/legalName/familyName1 Legal Last Name Y
/workers/person/legalName/formattedName Legal Full Name Y
/workers/person/preferredName/givenName Preferred First Name Y
/workers/person/highestEducationLevelCode Highest Education Level Y
/workers/workerID/idValue Worker ID Y
"""

ADP_FIXTURE_WITH_NA = """\
/workers/person/disabledIndicator Disabled Indicator NA
/workers/customFieldGroup/codeFields Custom Code Fields Y
"""


class TestAdpPathParser:
    """Test extracting ADP schema location + field name from PDF text."""

    def test_parses_simple_paths(self) -> None:
        module = _load_script()
        entries = module.parse_adp_entries(ADP_FIXTURE_PAGE)
        assert len(entries) >= 5

        paths = {e["schema_path"] for e in entries}
        assert "/workers/person/birthDate" in paths
        assert "/workers/person/communication/emails/emailUri" in paths

    def test_extracts_field_name(self) -> None:
        module = _load_script()
        entries = module.parse_adp_entries(ADP_FIXTURE_PAGE)
        by_path = {e["schema_path"]: e for e in entries}
        assert by_path["/workers/person/birthDate"]["field_name"] == "Birth Date"

    def test_extracts_description_with_note(self) -> None:
        module = _load_script()
        entries = module.parse_adp_entries(ADP_FIXTURE_PAGE)
        by_path = {e["schema_path"]: e for e in entries}
        birth = by_path["/workers/person/birthDate"]
        assert "Masked by default" in birth["description"]

    def test_field_name_only_no_note(self) -> None:
        module = _load_script()
        entries = module.parse_adp_entries(ADP_FIXTURE_PAGE)
        by_path = {e["schema_path"]: e for e in entries}
        race = by_path["/workers/person/raceCode"]
        assert race["field_name"] == "Race"
        # Description should be just the field name when no note
        assert race["description"] == "Race"

    def test_na_entries_included(self) -> None:
        module = _load_script()
        entries = module.parse_adp_entries(ADP_FIXTURE_WITH_NA)
        assert len(entries) >= 1
        paths = {e["schema_path"] for e in entries}
        assert "/workers/person/disabledIndicator" in paths
```

- [ ] **Step 2: Run tests; verify they fail**

```bash
uv run pytest tests/test_extract_pdf_dictionary.py -v -k "AdpPathParser"
```

Expected: all fail with `AttributeError`.

- [ ] **Step 3: Implement `parse_adp_entries`**

Add to `scripts/extract_pdf_dictionary.py`:

```python
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
        # Field names are typically 1-4 capitalized words. Notes follow.
        # Heuristic: split on the last period-space or identify where the
        # note starts. For simplicity, use the full middle text as both
        # field_name basis and description.
        #
        # Try to separate field name from note:
        # Field names don't usually contain periods. If there's a period,
        # everything after the first period-containing segment is a note.
        parts = middle_text.split(". ")
        if len(parts) > 1:
            # Could be "Birth Date Masked by default." -> note present
            # Heuristic: field name is short (1-5 words), notes are longer
            # Try: first few words that look like a label
            field_name = _extract_field_name(middle_text)
            description = middle_text
        else:
            field_name = middle_text
            description = middle_text

        entries.append(
            {
                "schema_path": schema_path,
                "field_name": field_name,
                "description": description,
            }
        )

    return entries


def _extract_field_name(text: str) -> str:
    """Extract the field name label from ADP middle text.

    The field name is typically 1-4 capitalized words at the start,
    before any note text (which often starts with a verb or lowercase).
    """
    words = text.split()
    field_words: list[str] = []
    for i, word in enumerate(words):
        # Field name words start with uppercase or are short connectors
        # Notes often start with a verb ("Masked", "Required") or article
        if i > 0 and (
            word[0].islower()
            or (i >= 2 and word[0].isupper() and not word.istitle())
        ):
            # Check if this looks like a note start
            if word.lower() in (
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
            ):
                break
        field_words.append(word.rstrip("."))
        if len(field_words) >= 5:
            break
    return " ".join(field_words) if field_words else text
```

- [ ] **Step 4: Run tests; verify they pass**

```bash
uv run pytest tests/test_extract_pdf_dictionary.py -v -k "AdpPathParser"
```

Expected: all five pass.

**Note:** The field-name extraction heuristic may need tuning against the real
PDF. The test fixtures establish the contract; implementation can be adjusted in
Task 11.

- [ ] **Step 5: Commit**

```bash
git add scripts/extract_pdf_dictionary.py \
        tests/test_extract_pdf_dictionary.py
git commit -m "feat(scripts): add ADP PDF path parser

Regex-based extraction of schema location, field name, and description
from ADP data dictionary PDF lines.
Tracked on #3516."
```

---

## Task 9: ADP path-to-column converter + matcher -- full TDD

**Purpose:** Convert ADP JSON paths like `/workers/person/birthDate` to staging
YAML column names like `person__birth_date`. Build the ADP YAML index and match
entries, skipping `ARRAY<STRUCT<...>>` columns.

**Files:**

- Modify: `scripts/extract_pdf_dictionary.py`
- Modify: `tests/test_extract_pdf_dictionary.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_extract_pdf_dictionary.py`:

```python
class TestAdpPathToColumn:
    """Test converting ADP JSON paths to staging YAML column names."""

    def test_simple_path(self) -> None:
        module = _load_script()
        assert module.adp_path_to_column("/workers/person/birthDate") == "person__birth_date"

    def test_nested_path(self) -> None:
        module = _load_script()
        assert (
            module.adp_path_to_column("/workers/person/legalName/givenName")
            == "person__legal_name__given_name"
        )

    def test_worker_dates(self) -> None:
        module = _load_script()
        assert (
            module.adp_path_to_column("/workers/workerDates/originalHireDate")
            == "worker_dates__original_hire_date"
        )

    def test_worker_id(self) -> None:
        module = _load_script()
        assert (
            module.adp_path_to_column("/workers/workerID/idValue")
            == "worker_id__id_value"
        )

    def test_deep_nested(self) -> None:
        module = _load_script()
        assert (
            module.adp_path_to_column(
                "/workers/person/legalAddress/countrySubdivisionLevel1"
            )
            == "person__legal_address__country_subdivision_level_1"
        )

    def test_communication_emails(self) -> None:
        module = _load_script()
        assert (
            module.adp_path_to_column(
                "/workers/person/communication/emails/emailUri"
            )
            == "person__communication__emails__email_uri"
        )


class TestBuildAdpYamlIndex:
    """Test building the ADP YAML column lookup index."""

    def test_index_contains_workers(self) -> None:
        module = _load_script()
        index = module.build_adp_yaml_index()
        assert "stg_adp_workforce_now__workers" in index

    def test_workers_has_scalar_columns(self) -> None:
        module = _load_script()
        index = module.build_adp_yaml_index()
        workers = index["stg_adp_workforce_now__workers"]
        # These are scalar columns that should be in the index
        assert "person__birth_date" in workers["columns"]
        assert "associate_oid" in workers["columns"]

    def test_array_struct_columns_flagged(self) -> None:
        module = _load_script()
        index = module.build_adp_yaml_index()
        workers = index["stg_adp_workforce_now__workers"]
        # ARRAY<STRUCT<...>> columns should be in skip set
        assert "work_assignments" in workers["skip_columns"]
        assert "photos" in workers["skip_columns"]
```

- [ ] **Step 2: Run tests; verify they fail**

```bash
uv run pytest tests/test_extract_pdf_dictionary.py -v -k "AdpPathToColumn or BuildAdpYamlIndex"
```

Expected: all fail with `AttributeError`.

- [ ] **Step 3: Implement `adp_path_to_column` and `build_adp_yaml_index`**

Add to `scripts/extract_pdf_dictionary.py`:

```python
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
    # Strip /workers/ prefix
    path = schema_path
    if path.startswith("/workers/"):
        path = path[len("/workers/"):]
    elif path.startswith("/workers"):
        path = path[len("/workers"):]

    # Split on / and convert each segment
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
```

- [ ] **Step 4: Run tests; verify they pass**

```bash
uv run pytest tests/test_extract_pdf_dictionary.py -v -k "AdpPathToColumn or BuildAdpYamlIndex"
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/extract_pdf_dictionary.py \
        tests/test_extract_pdf_dictionary.py
git commit -m "feat(scripts): add ADP path-to-column converter and YAML index

Converts ADP JSON paths to snake_case column names joined with '__'.
Builds YAML index that separates scalar columns from ARRAY<STRUCT>
columns (which are skipped during matching).
Tracked on #3516."
```

---

## Task 10: Script 1 ADP orchestration

**Purpose:** Wire up the full ADP extraction pipeline and implement
`_extract_adp`. Same pattern as PowerSchool: read PDF, parse entries, match
against YAML index, classify PII, output JSON.

**Files:**

- Modify: `scripts/extract_pdf_dictionary.py`
- Modify: `tests/test_extract_pdf_dictionary.py`

- [ ] **Step 1: Write the test for ADP mapping structure**

Append to `tests/test_extract_pdf_dictionary.py`:

```python
class TestBuildAdpMapping:
    """Test the ADP PDF-to-JSON mapping builder."""

    def test_mapping_structure(self) -> None:
        module = _load_script()
        pages = [ADP_FIXTURE_PAGE, ADP_FIXTURE_PAGE_2]
        yaml_index = {
            "stg_adp_workforce_now__workers": {
                "columns": {
                    "person__birth_date",
                    "person__race_code__code_value",
                    "person__gender_code__code_value",
                    "person__legal_name__given_name",
                    "person__legal_name__family_name_1",
                    "worker_dates__original_hire_date",
                    "worker_dates__termination_date",
                    "worker_id__id_value",
                },
                "skip_columns": {"work_assignments", "photos"},
            },
        }
        result = module.build_adp_mapping(pages, yaml_index)

        assert result["source"] == "adp"
        assert "entries" in result
        assert "stats" in result
        assert len(result["entries"]) > 0

    def test_pii_in_adp_mapping(self) -> None:
        module = _load_script()
        pages = [ADP_FIXTURE_PAGE]
        yaml_index = {
            "stg_adp_workforce_now__workers": {
                "columns": {
                    "person__birth_date",
                    "person__legal_address__postal_code",
                },
                "skip_columns": set(),
            },
        }
        result = module.build_adp_mapping(pages, yaml_index)
        entries_by_col = {e["column"]: e for e in result["entries"]}

        if "person__birth_date" in entries_by_col:
            assert entries_by_col["person__birth_date"]["contains_pii"] is True
        if "person__legal_address__postal_code" in entries_by_col:
            assert (
                entries_by_col["person__legal_address__postal_code"][
                    "contains_pii"
                ]
                is True
            )
```

- [ ] **Step 2: Run tests; verify they fail**

```bash
uv run pytest tests/test_extract_pdf_dictionary.py -v -k "BuildAdpMapping"
```

Expected: all fail with `AttributeError`.

- [ ] **Step 3: Implement `build_adp_mapping` and `_extract_adp`**

Add to `scripts/extract_pdf_dictionary.py`:

```python
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

        # Try exact match first
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
            # Check if any YAML column starts with or contains this path
            # (handles cases where PDF has parent path but YAML has child)
            found = False
            for yaml_col in all_yaml_columns:
                if yaml_col.startswith(column_name + "__"):
                    # This is a parent path -- skip, not a leaf
                    found = True
                    break
            if not found:
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
        # Find which model this column belongs to
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
```

Replace the `_extract_adp` placeholder:

```python
def _extract_adp(pdf_path: str) -> dict:
    """Extract ADP data dictionary from PDF."""
    from pypdf import PdfReader

    reader = PdfReader(pdf_path)
    pages = [page.extract_text() or "" for page in reader.pages]
    yaml_index = build_adp_yaml_index()
    return build_adp_mapping(pages, yaml_index)
```

- [ ] **Step 4: Run tests; verify they pass**

```bash
uv run pytest tests/test_extract_pdf_dictionary.py -v -k "BuildAdpMapping"
```

Expected: both tests pass.

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest tests/test_extract_pdf_dictionary.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/extract_pdf_dictionary.py \
        tests/test_extract_pdf_dictionary.py
git commit -m "feat(scripts): add ADP mapping builder and extraction orchestration

Full ADP extraction pipeline: PDF pages -> path parsing -> column matching
-> PII classification -> JSON output. Skips ARRAY<STRUCT> columns.
Tracked on #3516."
```

---

## Task 11: Run Script 1 against real PDFs, tune parsing, commit JSON inspection

**Purpose:** Run the extraction script against the actual PDFs stored in
`.claude/scratch/`. Inspect the output JSON, identify parsing failures, and tune
regex patterns. This is an iterative task -- the implementer should adjust
patterns and re-run until match rates are reasonable.

**Files:**

- Modify: `scripts/extract_pdf_dictionary.py` (tune regexes as needed)
- Inspect: `.claude/scratch/powerschool_dictionary.json`
- Inspect: `.claude/scratch/adp_dictionary.json`

- [ ] **Step 1: Run PowerSchool extraction**

```bash
uv run scripts/extract_pdf_dictionary.py \
    .claude/scratch/PSDB_PSSISDD_20241701.pdf powerschool
```

Inspect the summary output. Expected: several hundred matched entries out of
~3000+ PDF entries. The match rate depends on how many PS tables have
corresponding staging YAMLs.

- [ ] **Step 2: Inspect PowerSchool JSON**

```bash
uv run python -c "
import json
with open('.claude/scratch/powerschool_dictionary.json') as f:
    data = json.load(f)
print('Stats:', json.dumps(data['stats'], indent=2))
print('First 5 entries:')
for e in data['entries'][:5]:
    print(f\"  {e['model']}.{e['column']}: {e['description'][:60]}\")
print('First 10 unmatched PDF:')
for e in data['unmatched_pdf'][:10]:
    print(f\"  {e['table']}.{e['column']}\")
print('First 10 unmatched YAML:')
for e in data['unmatched_yaml'][:10]:
    print(f\"  {e['model']}.{e['column']}\")
"
```

Review the output. Common issues to fix:

- Table names that don't convert properly (e.g., `GPNode` should become
  `stg_powerschool__gpnode`)
- Column names that need special-case `pascal_to_snake` handling
- Multi-line descriptions that span page breaks
- Table description paragraphs being parsed as column entries

Tune `pascal_to_snake`, `_PS_COLUMN_RE`, and `extract_ps_table_name` as needed.
Re-run tests after each change.

- [ ] **Step 3: Run ADP extraction**

```bash
uv run scripts/extract_pdf_dictionary.py \
    .claude/scratch/Worker_Management_API_Guide_for_ADP_Workforce_Now.pdf adp
```

Inspect the summary. Expected: moderate match rate -- the ADP PDF covers the
full API but the staging YAML only has `stg_adp_workforce_now__workers`.

- [ ] **Step 4: Inspect ADP JSON**

```bash
uv run python -c "
import json
with open('.claude/scratch/adp_dictionary.json') as f:
    data = json.load(f)
print('Stats:', json.dumps(data['stats'], indent=2))
print('First 5 entries:')
for e in data['entries'][:5]:
    print(f\"  {e['model']}.{e['column']}: {e['description'][:60]}\")
print('First 10 unmatched YAML:')
for e in data['unmatched_yaml'][:10]:
    print(f\"  {e['model']}.{e['column']}\")
"
```

Tune `parse_adp_entries`, `_extract_field_name`, and `adp_path_to_column` as
needed. Common issues:

- Path segments with consecutive capitals (e.g., `workerID`)
- Nested paths that match parent YAML columns instead of leaf columns
- Field name extraction splitting incorrectly

- [ ] **Step 5: Re-run all unit tests to confirm tuning didn't break anything**

```bash
uv run pytest tests/test_extract_pdf_dictionary.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit any tuning changes**

```bash
git add scripts/extract_pdf_dictionary.py \
        tests/test_extract_pdf_dictionary.py
git commit -m "fix(scripts): tune PDF parsing for real PowerSchool and ADP PDFs

Adjusted regex patterns and case conversion after running against actual
source-system PDFs. Match rates validated via JSON output inspection.
Tracked on #3516."
```

---

## Task 12: YAML enrichment reader/writer -- full TDD

**Purpose:** Read a staging YAML file, enrich columns with descriptions and PII
flags from the JSON mapping, and write back. Preserves existing non-empty
descriptions. Uses `sort_keys=False` to maintain key order.

**Files:**

- Modify: `scripts/enrich_staging_descriptions.py`
- Modify: `tests/test_enrich_staging_descriptions.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_enrich_staging_descriptions.py`:

```python
import yaml

# Minimal YAML fixture representing a staging model
YAML_FIXTURE = """\
models:
  - name: stg_powerschool__students
    columns:
      - name: id
        data_type: int64
        data_tests:
          - unique:
              config:
                severity: error
      - name: first_name
        data_type: string
      - name: ssn
        data_type: string
      - name: grade_level
        data_type: string
        description: Existing hand-written description.
"""

# Mapping entries for the fixture
MAPPING_ENTRIES = [
    {
        "model": "stg_powerschool__students",
        "column": "id",
        "description": "Auto-incrementing unique record identifier.",
        "contains_pii": False,
    },
    {
        "model": "stg_powerschool__students",
        "column": "first_name",
        "description": "The student's legal first name.",
        "contains_pii": True,
    },
    {
        "model": "stg_powerschool__students",
        "column": "ssn",
        "description": "Social security number.",
        "contains_pii": True,
    },
    {
        "model": "stg_powerschool__students",
        "column": "grade_level",
        "description": "PDF description that should be IGNORED.",
        "contains_pii": False,
    },
]


class TestEnrichYamlData:
    """Test the YAML enrichment function."""

    def test_adds_description_to_empty_column(self) -> None:
        module = _load_script()
        doc = yaml.safe_load(YAML_FIXTURE)
        result = module.enrich_yaml_data(doc, MAPPING_ENTRIES)
        columns = result["models"][0]["columns"]
        by_name = {c["name"]: c for c in columns}
        assert by_name["first_name"]["description"] == (
            "The student's legal first name."
        )

    def test_preserves_existing_description(self) -> None:
        module = _load_script()
        doc = yaml.safe_load(YAML_FIXTURE)
        result = module.enrich_yaml_data(doc, MAPPING_ENTRIES)
        columns = result["models"][0]["columns"]
        by_name = {c["name"]: c for c in columns}
        assert by_name["grade_level"]["description"] == (
            "Existing hand-written description."
        )

    def test_adds_pii_flag(self) -> None:
        module = _load_script()
        doc = yaml.safe_load(YAML_FIXTURE)
        result = module.enrich_yaml_data(doc, MAPPING_ENTRIES)
        columns = result["models"][0]["columns"]
        by_name = {c["name"]: c for c in columns}
        assert by_name["ssn"]["config"]["meta"]["contains_pii"] is True
        assert by_name["id"]["config"]["meta"]["contains_pii"] is False

    def test_pii_flag_overwrites_existing(self) -> None:
        """PII classification from PDF is authoritative -- overwrites."""
        module = _load_script()
        fixture_with_pii = YAML_FIXTURE.replace(
            "      - name: ssn\n        data_type: string",
            (
                "      - name: ssn\n        data_type: string\n"
                "        config:\n          meta:\n            contains_pii: false"
            ),
        )
        doc = yaml.safe_load(fixture_with_pii)
        result = module.enrich_yaml_data(doc, MAPPING_ENTRIES)
        columns = result["models"][0]["columns"]
        by_name = {c["name"]: c for c in columns}
        assert by_name["ssn"]["config"]["meta"]["contains_pii"] is True

    def test_preserves_data_tests(self) -> None:
        module = _load_script()
        doc = yaml.safe_load(YAML_FIXTURE)
        result = module.enrich_yaml_data(doc, MAPPING_ENTRIES)
        columns = result["models"][0]["columns"]
        by_name = {c["name"]: c for c in columns}
        assert "data_tests" in by_name["id"]
        assert len(by_name["id"]["data_tests"]) == 1

    def test_returns_enrichment_stats(self) -> None:
        module = _load_script()
        doc = yaml.safe_load(YAML_FIXTURE)
        result, stats = module.enrich_yaml_data(doc, MAPPING_ENTRIES, return_stats=True)
        assert stats["enriched"] == 3  # id, first_name, ssn
        assert stats["skipped"] == 1  # grade_level (existing description)
        assert stats["total"] == 4

    def test_unmatched_columns_not_modified(self) -> None:
        """Columns with no mapping entry stay untouched."""
        module = _load_script()
        doc = yaml.safe_load(YAML_FIXTURE)
        # Only provide mapping for 'id'
        partial_entries = [MAPPING_ENTRIES[0]]
        result = module.enrich_yaml_data(doc, partial_entries)
        columns = result["models"][0]["columns"]
        by_name = {c["name"]: c for c in columns}
        assert "description" not in by_name["first_name"]
        assert "config" not in by_name["first_name"]
```

- [ ] **Step 2: Run tests; verify they fail**

```bash
uv run pytest tests/test_enrich_staging_descriptions.py -v -k "EnrichYamlData"
```

Expected: all fail with `AttributeError`.

- [ ] **Step 3: Implement `enrich_yaml_data`**

Add to `scripts/enrich_staging_descriptions.py`:

```python
import yaml


def enrich_yaml_data(
    doc: dict,
    mapping_entries: list[dict],
    return_stats: bool = False,
) -> dict | tuple[dict, dict[str, int]]:
    """Enrich a YAML document with descriptions and PII flags.

    Args:
        doc: Parsed YAML document (from yaml.safe_load).
        mapping_entries: List of mapping entry dicts from JSON.
        return_stats: If True, return (doc, stats) tuple.

    Returns:
        Enriched YAML document dict, or (doc, stats) if return_stats=True.

    Behavior:
        - description: added only if absent or empty.
        - config.meta.contains_pii: always written (authoritative).
        - Columns with no mapping entry are not modified.
    """
    # Build lookup: (model, column) -> entry
    lookup: dict[tuple[str, str], dict] = {}
    for entry in mapping_entries:
        key = (entry["model"], entry["column"])
        lookup[key] = entry

    stats = {"enriched": 0, "skipped": 0, "total": 0}

    for model in doc.get("models", []) or []:
        model_name = model["name"]
        for column in model.get("columns", []) or []:
            stats["total"] += 1
            col_name = column["name"]
            key = (model_name, col_name)
            if key not in lookup:
                continue

            entry = lookup[key]

            # Description: add only if absent or empty
            existing_desc = column.get("description", "")
            if existing_desc and str(existing_desc).strip():
                stats["skipped"] += 1
            else:
                column["description"] = entry["description"]
                stats["enriched"] += 1

            # PII flag: always write (authoritative)
            config = column.setdefault("config", {})
            meta = config.setdefault("meta", {})
            meta["contains_pii"] = entry["contains_pii"]

    if return_stats:
        return doc, stats
    return doc
```

- [ ] **Step 4: Run tests; verify they pass**

```bash
uv run pytest tests/test_enrich_staging_descriptions.py -v -k "EnrichYamlData"
```

Expected: all seven pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/enrich_staging_descriptions.py \
        tests/test_enrich_staging_descriptions.py
git commit -m "feat(scripts): add YAML enrichment reader/writer

Enriches staging YAML with descriptions (skip if existing) and PII flags
(always overwrite). Preserves data_tests and other existing properties.
Tracked on #3516."
```

---

## Task 13: Script 2 orchestration + stdout reporting

**Purpose:** Implement the full `main()` for the enrichment script: read JSON
mapping file(s), group entries by model, find corresponding YAML files, enrich
and rewrite them, and print a summary.

**Files:**

- Modify: `scripts/enrich_staging_descriptions.py`
- Modify: `tests/test_enrich_staging_descriptions.py`

- [ ] **Step 1: Write the test for YAML file discovery**

Append to `tests/test_enrich_staging_descriptions.py`:

```python
class TestFindYamlFile:
    """Test finding the YAML file for a given model name."""

    def test_finds_powerschool_students(self) -> None:
        module = _load_script()
        path = module.find_yaml_file("stg_powerschool__students")
        assert path is not None
        assert path.name == "stg_powerschool__students.yml"
        assert path.exists()

    def test_finds_adp_workers(self) -> None:
        module = _load_script()
        path = module.find_yaml_file("stg_adp_workforce_now__workers")
        assert path is not None
        assert path.name == "stg_adp_workforce_now__workers.yml"
        assert path.exists()

    def test_returns_none_for_nonexistent(self) -> None:
        module = _load_script()
        path = module.find_yaml_file("stg_nonexistent__model")
        assert path is None
```

- [ ] **Step 2: Write the test for YAML writing**

Append to `tests/test_enrich_staging_descriptions.py`:

```python
import tempfile
from pathlib import Path


class TestWriteYaml:
    """Test YAML write output format."""

    def test_write_preserves_key_order(self) -> None:
        module = _load_script()
        doc = yaml.safe_load(YAML_FIXTURE)
        result = module.enrich_yaml_data(doc, MAPPING_ENTRIES)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as fh:
            module.write_yaml(result, fh)
            tmp_path = Path(fh.name)

        try:
            content = tmp_path.read_text(encoding="utf-8")
            # models: should appear before columns
            assert content.index("models:") < content.index("columns:")
            # name: should appear before data_type:
            assert content.index("- name:") < content.index("data_type:")
        finally:
            tmp_path.unlink()

    def test_write_roundtrip(self) -> None:
        module = _load_script()
        doc = yaml.safe_load(YAML_FIXTURE)
        result = module.enrich_yaml_data(doc, MAPPING_ENTRIES)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as fh:
            module.write_yaml(result, fh)
            tmp_path = Path(fh.name)

        try:
            with tmp_path.open(encoding="utf-8") as fh:
                reloaded = yaml.safe_load(fh)
            columns = reloaded["models"][0]["columns"]
            by_name = {c["name"]: c for c in columns}
            assert by_name["first_name"]["description"] == (
                "The student's legal first name."
            )
            assert by_name["ssn"]["config"]["meta"]["contains_pii"] is True
        finally:
            tmp_path.unlink()
```

- [ ] **Step 3: Run tests; verify they fail**

```bash
uv run pytest tests/test_enrich_staging_descriptions.py -v -k "FindYamlFile or WriteYaml"
```

Expected: all fail with `AttributeError`.

- [ ] **Step 4: Implement `find_yaml_file`, `write_yaml`, and `main()`**

Add to `scripts/enrich_staging_descriptions.py`:

```python
import json
import sys
from pathlib import Path
from typing import TextIO

# All directories that may contain staging YAML files
STAGING_YAML_DIRS: tuple[Path, ...] = (
    Path("src/dbt/powerschool/models/sis/staging/properties"),
    Path("src/dbt/kipptaf/models/powerschool/staging/properties"),
    Path("src/dbt/kipptaf/models/adp/workforce_now/api/staging/properties"),
    Path("src/dbt/kipptaf/models/adp/workforce_now/sftp/staging/properties"),
    Path("src/dbt/kipptaf/models/adp/workforce_manager/staging/properties"),
    Path("src/dbt/kipptaf/models/adp/payroll/staging/properties"),
)


def find_yaml_file(model_name: str) -> Path | None:
    """Find the YAML properties file for a given staging model name.

    Searches all known staging YAML directories for a file named
    <model_name>.yml.
    """
    for directory in STAGING_YAML_DIRS:
        if not directory.exists():
            continue
        candidate = directory / f"{model_name}.yml"
        if candidate.exists():
            return candidate
    return None


def write_yaml(doc: dict, fh: TextIO) -> None:
    """Write YAML document preserving key order."""
    yaml.dump(
        doc,
        fh,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=88,
    )


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: uv run scripts/enrich_staging_descriptions.py "
            "<json_path> [<json_path> ...]",
            file=sys.stderr,
        )
        sys.exit(1)

    # Load all mapping files
    all_entries: list[dict] = []
    for json_path in sys.argv[1:]:
        with open(json_path, encoding="utf-8") as fh:
            data = json.load(fh)
        all_entries.extend(data.get("entries", []))
        print(f"Loaded {len(data.get('entries', []))} entries from {json_path}")

    # Group entries by model
    entries_by_model: dict[str, list[dict]] = {}
    for entry in all_entries:
        model = entry["model"]
        entries_by_model.setdefault(model, []).append(entry)

    # Process each model
    total_enriched = 0
    total_skipped = 0
    total_columns = 0
    files_modified = 0

    for model_name in sorted(entries_by_model):
        yaml_path = find_yaml_file(model_name)
        if yaml_path is None:
            print(f"  SKIP {model_name}: YAML file not found")
            continue

        with yaml_path.open(encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)

        if not doc:
            print(f"  SKIP {model_name}: empty YAML")
            continue

        result, stats = enrich_yaml_data(
            doc, entries_by_model[model_name], return_stats=True
        )

        if stats["enriched"] > 0:
            with yaml_path.open("w", encoding="utf-8") as fh:
                write_yaml(result, fh)
            files_modified += 1

        total_enriched += stats["enriched"]
        total_skipped += stats["skipped"]
        total_columns += stats["total"]

        print(
            f"  {model_name}: "
            f"{stats['enriched']} enriched, "
            f"{stats['skipped']} skipped (existing), "
            f"{stats['total']} total"
        )

    print(f"\nSummary:")
    print(f"  Files modified: {files_modified}")
    print(f"  Columns enriched: {total_enriched}")
    print(f"  Columns skipped (existing desc): {total_skipped}")
    print(f"  Total columns processed: {total_columns}")
```

- [ ] **Step 5: Run tests; verify they pass**

```bash
uv run pytest tests/test_enrich_staging_descriptions.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/enrich_staging_descriptions.py \
        tests/test_enrich_staging_descriptions.py
git commit -m "feat(scripts): add YAML file discovery, writer, and main() orchestration

Complete Script 2: reads JSON mappings, finds YAML files, enriches them
with descriptions and PII flags, writes back with key order preserved.
Prints per-file and summary stats.
Tracked on #3516."
```

---

## Task 14: Run Script 2 against real staging YAMLs, inspect diff

**Purpose:** Run the enrichment script against the real staging YAML files using
the JSON mapping files produced in Task 11. Inspect the git diff to verify the
changes look correct. This is the final validation step before committing the
YAML changes.

**Files:**

- Modify: `src/dbt/powerschool/models/**/staging/properties/*.yml`
- Modify: `src/dbt/kipptaf/models/**/staging/properties/*.yml`

- [ ] **Step 1: Run the enrichment script**

```bash
uv run scripts/enrich_staging_descriptions.py \
    .claude/scratch/powerschool_dictionary.json \
    .claude/scratch/adp_dictionary.json
```

Inspect the summary output. Expected:

- Many files modified for PowerSchool
- 1+ files modified for ADP
- Some columns skipped (existing descriptions)

- [ ] **Step 2: Inspect the diff**

```bash
git diff --stat
```

Verify that only `*.yml` files under staging `properties/` directories were
modified.

```bash
git diff -- src/dbt/powerschool/models/sis/staging/properties/stg_powerschool__students.yml | head -60
```

Check that:

- `description:` lines were added to columns that lacked them
- `config.meta.contains_pii:` was added
- Existing descriptions were preserved (the `grade_level` pattern)
- Key order looks reasonable (name, data_type, description, config)
- No unexpected changes to `data_tests:`

```bash
git diff -- src/dbt/kipptaf/models/adp/workforce_now/api/staging/properties/stg_adp_workforce_now__workers.yml | head -60
```

Check ADP changes similarly.

- [ ] **Step 3: Spot-check PII classifications**

```bash
git diff -- src/dbt/ | grep "contains_pii: true" | head -20
```

Verify that PII-flagged columns are genuinely PII (names, SSN, addresses, etc.).

```bash
git diff -- src/dbt/ | grep "contains_pii: false" | head -20
```

Verify that non-PII columns are genuinely non-PII.

- [ ] **Step 4: Run trunk check on modified files**

```bash
/workspaces/teamster/.trunk/tools/trunk check --ci
```

Fix any formatting issues. Trunk fmt should handle most automatically via the
pre-commit hook.

- [ ] **Step 5: Run all unit tests**

```bash
uv run pytest tests/test_extract_pdf_dictionary.py tests/test_enrich_staging_descriptions.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit the enriched YAML files**

Stage all modified YAML files. Use `git add -u` since we're only modifying
existing files:

```bash
git add -u
git commit -m "feat(dbt): enrich staging descriptions from source dictionaries

Applied descriptions and contains_pii flags to PowerSchool and ADP
staging YAML files from source-system PDF data dictionaries.
Comments in PS YAMLs are lost (accepted trade-off per spec).
Tracked on #3516."
```

---

## Task 15: Update scripts/CLAUDE.md catalog

**Purpose:** Document both new scripts in the `scripts/` catalog.

**Files:**

- Modify: `scripts/CLAUDE.md`

- [ ] **Step 1: Edit the catalog table**

In `scripts/CLAUDE.md`, insert two new rows in the catalog table in alphabetical
position. Use the Edit tool with:

- `old_string`:

  ```text
  | `dbt-yaml.py`                                 | Parse and transform dbt YAML files                  |
  | `gen-automations-doc.py`                      | Regenerate `docs/reference/automations.md`          |
  ```

- `new_string`:

  ```text
  | `dbt-yaml.py`                                 | Parse and transform dbt YAML files                  |
  | `enrich_staging_descriptions.py`              | Enrich staging YAMLs with descriptions and PII flags|
  | `extract_pdf_dictionary.py`                   | Extract column descriptions from source-system PDFs |
  | `gen-automations-doc.py`                      | Regenerate `docs/reference/automations.md`          |
  ```

- [ ] **Step 2: Commit**

```bash
git add scripts/CLAUDE.md
git commit -m "docs(scripts): catalog data dictionary enrichment scripts

Tracked on #3516."
```

---

## Post-plan handoff

After Task 15, the worktree contains:

- `scripts/extract_pdf_dictionary.py` -- Script 1: PDF extraction + JSON mapping
- `scripts/enrich_staging_descriptions.py` -- Script 2: JSON to YAML enrichment
- `tests/test_extract_pdf_dictionary.py` -- unit tests for Script 1 helpers
- `tests/test_enrich_staging_descriptions.py` -- unit tests for Script 2 helpers
- Enriched staging YAML files under `src/dbt/powerschool/` and
  `src/dbt/kipptaf/` with `description:` and `config.meta.contains_pii:`
- Updated `scripts/CLAUDE.md` catalog

### Review surface

The PR diff shows all YAML changes inline. Reviewers should:

1. Spot-check descriptions for accuracy (do they match the source-system PDF?)
2. Verify PII classifications (are sensitive fields flagged correctly?)
3. Review unmatched lists in the JSON artifacts (`.claude/scratch/`) for
   coverage gaps
4. Confirm that existing hand-written descriptions were preserved

### Known limitations

- **Comment loss:** `pyyaml` does not preserve YAML comments. Commented-out
  columns in PowerSchool YAMLs are removed. The spec accepts this trade-off.
- **Key reordering:** `pyyaml` with `sort_keys=False` preserves insertion order
  but may not perfectly match the original file's key order. `trunk fmt`
  normalizes formatting afterward.
- **Iterative tuning:** Tasks 11 and 14 are inherently iterative. The first run
  against real PDFs will likely require regex adjustments. The test fixtures
  establish the contract; implementation details may shift.
- **ADP SFTP models:** The ADP PDF covers the API only. The 4 SFTP staging
  models (`additional_earnings_report`, `employee_memberships`,
  `pension_and_benefits_enrollments`, `workers`) are not enriched by this
  script.
- **kipptaf PowerSchool staging:** kipptaf has ~34 PS staging models that
  re-stage source-project models. The script searches both directories, so these
  will be enriched if matching PDF entries exist.

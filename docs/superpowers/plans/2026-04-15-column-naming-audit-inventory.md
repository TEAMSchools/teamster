# Column Naming Audit Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python script that generates a CSV inventory of every column
in every `kipptaf` mart model (plus structural-addition rows), ready for human
review in a Google Sheet. Terminal state: initial CSV committed to
`docs/superpowers/specs/`; no dbt model changes yet.

**Architecture:** Single PEP 723 script under `scripts/` with underscore name
(for test importability via `importlib.util`). Reads YAML properties files under
`src/dbt/kipptaf/models/marts/{bridges,dimensions,facts}/properties/` using
stdlib via `yaml` (transitively available from `dbt-core`). Emits CSV via stdlib
`csv`. Pure functions (no side effects) extracted for unit testing; `main()`
orchestrates file I/O and writes the output CSV.

**Tech Stack:** Python 3.13, `uv run`, `pyyaml`, stdlib `csv`, `pytest`.

**Scope note:** This plan covers **only** the inventory-generation phase. A
follow-up plan covers the implementation script that reads the **approved** CSV
(after human sheet review) and emits the SQL + YAML edits.

**Design reference:**
[2026-04-15-column-naming-audit.md](../specs/2026-04-15-column-naming-audit.md)

---

## File Structure

| File                                                                  | Responsibility                                                              |
| --------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| `scripts/gen_column_naming_audit_inventory.py`                        | CREATE — main script; exposes pure helpers + `main()`.                      |
| `tests/test_gen_column_naming_audit_inventory.py`                     | CREATE — pytest unit tests; loads the script via `importlib.util`.          |
| `tests/fixtures/mart_yaml/dim_sample.yml`                             | CREATE — minimal YAML fixture for `_read_mart_yaml` tests.                  |
| `docs/superpowers/specs/2026-04-15-column-naming-audit-inventory.csv` | CREATE — output CSV, committed so reviewers can import into the sheet.      |
| `scripts/CLAUDE.md`                                                   | MODIFY — add the new script to the catalog table (one row, alphabetically). |

---

## Conventions Used In This Plan

- All paths are relative to the worktree root
  `/workspaces/teamster/.worktrees/cbini/refactor/claude-column-naming-full-audit`.
- All shell commands are run from the worktree root unless noted.
- Python runs via `uv run` — never bare `python`.
- All commits use conventional commits (`feat(scripts): ...`, `test: ...`,
  `docs: ...`).
- Stage changes with `git add <explicit paths>` in this plan — subagents must
  name specific files per the project CLAUDE.md.
- `trunk fmt` is handled by the PostToolUse hook — do not run manually.

---

## Task 1: Create the script skeleton and importable test harness

**Files:**

- Create: `scripts/gen_column_naming_audit_inventory.py`
- Create: `tests/test_gen_column_naming_audit_inventory.py`

- [ ] **Step 1: Write the minimal script with PEP 723 header and module
      docstring**

Write to `scripts/gen_column_naming_audit_inventory.py`:

```python
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


def main() -> None:
    raise NotImplementedError


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write the test harness that imports the script via
      `importlib.util`**

Write to `tests/test_gen_column_naming_audit_inventory.py`:

```python
"""Unit tests for scripts/gen_column_naming_audit_inventory.py.

The script filename uses underscores specifically so we can import it.
We use importlib.util rather than changing project-wide pytest config,
keeping the import pattern local to this test file.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO_ROOT / "scripts" / "gen_column_naming_audit_inventory.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "gen_column_naming_audit_inventory", _SCRIPT
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

- [ ] **Step 3: Run the smoke test and verify it passes**

Run:

```bash
uv run pytest tests/test_gen_column_naming_audit_inventory.py -v
```

Expected: `test_script_module_loads PASSED`.

- [ ] **Step 4: Commit**

```bash
git add scripts/gen_column_naming_audit_inventory.py \
        tests/test_gen_column_naming_audit_inventory.py
git commit -m "feat(scripts): scaffold column naming audit inventory script

Empty skeleton with PEP 723 header and importable-via-importlib test harness.
Tracked on #3643."
```

---

## Task 2: `_flatten_description` — collapse multiline YAML descriptions

**Purpose:** YAML descriptions use block scalars (`>-`) that unfold into strings
with embedded newlines and extra whitespace. The CSV needs them as single-line
text. This helper flattens any whitespace sequence to one space and strips
leading/trailing whitespace.

**Files:**

- Modify: `scripts/gen_column_naming_audit_inventory.py`
- Modify: `tests/test_gen_column_naming_audit_inventory.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_gen_column_naming_audit_inventory.py`:

```python
def test_flatten_description_collapses_internal_whitespace() -> None:
    module = _load_script()
    result = module._flatten_description("Student\n  date   of\tbirth.")
    assert result == "Student date of birth."


def test_flatten_description_strips_edges() -> None:
    module = _load_script()
    result = module._flatten_description("\n  hello world  \n")
    assert result == "hello world"


def test_flatten_description_handles_empty_and_none() -> None:
    module = _load_script()
    assert module._flatten_description("") == ""
    assert module._flatten_description(None) == ""
```

- [ ] **Step 2: Run tests; verify they fail**

Run:

```bash
uv run pytest tests/test_gen_column_naming_audit_inventory.py -v -k flatten_description
```

Expected: three tests fail with
`AttributeError: module ... has no attribute '_flatten_description'`.

- [ ] **Step 3: Implement `_flatten_description`**

Insert above `main()` in `scripts/gen_column_naming_audit_inventory.py`:

```python
import re

_WS_RE = re.compile(r"\s+")


def _flatten_description(text: str | None) -> str:
    """Collapse whitespace runs to single spaces and strip edges."""
    if not text:
        return ""
    return _WS_RE.sub(" ", text).strip()
```

- [ ] **Step 4: Run tests; verify they pass**

Run:

```bash
uv run pytest tests/test_gen_column_naming_audit_inventory.py -v -k flatten_description
```

Expected: three tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/gen_column_naming_audit_inventory.py \
        tests/test_gen_column_naming_audit_inventory.py
git commit -m "feat(scripts): add _flatten_description helper

Collapses multiline YAML description strings to single-line CSV-safe text.
Tracked on #3643."
```

---

## Task 3: `_domain_for_model` — classify model name to audit domain

**Purpose:** Group CSV rows by domain (Conformed, Student, Staff, Course,
Assessment, College, Observation, Attendance, Behavioral, Gradebook, Survey,
Talent, Staffing, IT). Reviewers filter the sheet by domain to focus their
review passes. Domain is inferred from the model name prefix.

**Files:**

- Modify: `scripts/gen_column_naming_audit_inventory.py`
- Modify: `tests/test_gen_column_naming_audit_inventory.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_gen_column_naming_audit_inventory.py`:

```python
def test_domain_for_model_conformed() -> None:
    module = _load_script()
    assert module._domain_for_model("dim_dates") == "Conformed"
    assert module._domain_for_model("dim_locations") == "Conformed"
    assert module._domain_for_model("dim_regions") == "Conformed"
    assert module._domain_for_model("dim_school_calendars") == "Conformed"
    assert module._domain_for_model("dim_terms") == "Conformed"


def test_domain_for_model_student() -> None:
    module = _load_script()
    assert module._domain_for_model("dim_students") == "Student"
    assert module._domain_for_model("dim_student_enrollments") == "Student"
    assert module._domain_for_model("bridge_student_contacts") == "Student"
    assert module._domain_for_model("fct_student_attendance_daily") == "Attendance"


def test_domain_for_model_staff() -> None:
    module = _load_script()
    assert module._domain_for_model("dim_staff") == "Staff"
    assert module._domain_for_model("dim_staff_work_assignments") == "Staff"
    assert module._domain_for_model("dim_staff_observation_types") == "Observation"
    assert module._domain_for_model("fct_staff_observations") == "Observation"


def test_domain_for_model_other_domains() -> None:
    module = _load_script()
    assert module._domain_for_model("dim_assessments") == "Assessment"
    assert module._domain_for_model("dim_colleges") == "College"
    assert module._domain_for_model("fct_behavioral_incidents") == "Behavioral"
    assert module._domain_for_model("fct_family_communications") == "Behavioral"
    assert module._domain_for_model("fct_grades_term") == "Gradebook"
    assert module._domain_for_model("dim_surveys") == "Survey"
    assert module._domain_for_model("dim_job_postings") == "Talent"
    assert module._domain_for_model("dim_staffing_positions") == "Staffing"
    assert module._domain_for_model("fct_support_tickets") == "IT"


def test_domain_for_model_course() -> None:
    module = _load_script()
    assert module._domain_for_model("dim_courses") == "Course"
    assert module._domain_for_model("dim_course_sections") == "Course"
    assert module._domain_for_model("bridge_course_section_teachers") == "Course"


def test_domain_for_model_unknown_returns_uncategorized() -> None:
    module = _load_script()
    assert module._domain_for_model("dim_wild_card_thing") == "Uncategorized"
```

- [ ] **Step 2: Run tests; verify they fail**

Run:

```bash
uv run pytest tests/test_gen_column_naming_audit_inventory.py -v -k domain_for_model
```

Expected: all fail with `AttributeError`.

- [ ] **Step 3: Implement `_domain_for_model`**

Add to `scripts/gen_column_naming_audit_inventory.py` below
`_flatten_description`:

```python
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
```

- [ ] **Step 4: Run tests; verify they pass**

Run:

```bash
uv run pytest tests/test_gen_column_naming_audit_inventory.py -v -k domain_for_model
```

Expected: all six pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/gen_column_naming_audit_inventory.py \
        tests/test_gen_column_naming_audit_inventory.py
git commit -m "feat(scripts): add _domain_for_model classifier

Maps mart model names to audit domains for sheet-level filtering.
Tracked on #3643."
```

---

## Task 4: `_plumbing_columns` — constant set of columns slated for removal

**Purpose:** Known plumbing column names (e.g., `_dbt_source_relation`) get a
default `action=remove` and `rule_ref=plumbing` in the CSV. The list is
conservative — edge cases are flagged for review rather than auto-removed.

**Files:**

- Modify: `scripts/gen_column_naming_audit_inventory.py`
- Modify: `tests/test_gen_column_naming_audit_inventory.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_gen_column_naming_audit_inventory.py`:

```python
def test_plumbing_columns_includes_dbt_source_relation() -> None:
    module = _load_script()
    assert "_dbt_source_relation" in module._plumbing_columns()


def test_plumbing_columns_returns_frozenset() -> None:
    module = _load_script()
    result = module._plumbing_columns()
    assert isinstance(result, frozenset)
```

- [ ] **Step 2: Run tests; verify they fail**

Run:

```bash
uv run pytest tests/test_gen_column_naming_audit_inventory.py -v -k plumbing
```

Expected: both fail with `AttributeError`.

- [ ] **Step 3: Implement `_plumbing_columns`**

Add to `scripts/gen_column_naming_audit_inventory.py`:

```python
_PLUMBING_COLUMNS: frozenset[str] = frozenset(
    [
        "_dbt_source_relation",
    ]
)


def _plumbing_columns() -> frozenset[str]:
    """Columns whose default audit action is 'remove' (plumbing)."""
    return _PLUMBING_COLUMNS
```

- [ ] **Step 4: Run tests; verify they pass**

Run:

```bash
uv run pytest tests/test_gen_column_naming_audit_inventory.py -v -k plumbing
```

Expected: both pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/gen_column_naming_audit_inventory.py \
        tests/test_gen_column_naming_audit_inventory.py
git commit -m "feat(scripts): add _plumbing_columns set

Seeds the audit with known plumbing columns that default to action=remove.
Additional edge cases are flagged for reviewer judgment.
Tracked on #3643."
```

---

## Task 5: `_initial_rename_guess` — pre-populate obvious renames

**Purpose:** For column names that appear in the existing 67-rename audit list
(Issue #3643 original), pre-populate `proposed_name` and `rule_ref` so reviewers
have a starting point. Reviewers can accept, reject, or alter. The guess list is
bounded — only high-confidence source-jargon cases are encoded; everything else
defaults to `keep` with empty proposal.

**Files:**

- Modify: `scripts/gen_column_naming_audit_inventory.py`
- Modify: `tests/test_gen_column_naming_audit_inventory.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_gen_column_naming_audit_inventory.py`:

```python
def test_initial_rename_guess_student_number() -> None:
    module = _load_script()
    result = module._initial_rename_guess("student_number")
    assert result == ("local_student_identifier", "R1")


def test_initial_rename_guess_employee_number() -> None:
    module = _load_script()
    result = module._initial_rename_guess("employee_number")
    assert result == ("local_staff_identifier", "R2")


def test_initial_rename_guess_formatted_name() -> None:
    module = _load_script()
    result = module._initial_rename_guess("formatted_name")
    assert result == ("full_name", "R6")


def test_initial_rename_guess_unmapped_returns_none() -> None:
    module = _load_script()
    assert module._initial_rename_guess("student_key") is None
    assert module._initial_rename_guess("made_up_column") is None
```

- [ ] **Step 2: Run tests; verify they fail**

Run:

```bash
uv run pytest tests/test_gen_column_naming_audit_inventory.py -v -k initial_rename
```

Expected: all fail with `AttributeError`.

- [ ] **Step 3: Implement `_initial_rename_guess`**

Add to `scripts/gen_column_naming_audit_inventory.py`:

```python
# Pre-populated rename guesses carried over from the original 67-column
# audit. Each entry is (current_name, (proposed_name, rule_ref)). The rule
# references the rubric section in
# docs/superpowers/specs/2026-04-15-column-naming-audit.md.
_RENAME_GUESSES: dict[str, tuple[str, str]] = {
    # Rule 1 — strip source-system names (student identifier)
    "student_number": ("local_student_identifier", "R1"),
    # Rule 2 — no KIPP-specific language (staff identifier)
    "employee_number": ("local_staff_identifier", "R2"),
    "teacher_employee_number": ("teacher_staff_identifier", "R2"),
    "observer_employee_number": ("observer_staff_identifier", "R2"),
    "teammate_employee_number": ("teammate_staff_identifier", "R2"),
    "recruiter_employee_number": ("recruiter_staff_identifier", "R2"),
    # Rule 6 — Ed-Fi / plain English for person names
    "formatted_name": ("full_name", "R6"),
    "family_name_1": ("last_name", "R6"),
    "given_name": ("first_name", "R6"),
    "manager_formatted_name": ("manager_full_name", "R6"),
    "manager_family_name_1": ("manager_last_name", "R6"),
    "manager_given_name": ("manager_first_name", "R6"),
    # Rule 1 — PowerSchool identifier stripping
    "powerschool_school_id": ("sis_school_id", "R1"),
    "deanslist_school_id": ("behavior_system_school_id", "R1"),
    "powerschool_term_id": ("sis_term_id", "R1"),
    "powerschool_year_id": ("sis_year_id", "R1"),
    "powerschool_person_id": ("contact_person_id", "R1"),
    "sections_dcid": ("section_id", "R1"),
    "teachernumber": ("teacher_number", "R1"),
}


def _initial_rename_guess(column_name: str) -> tuple[str, str] | None:
    """Return (proposed_name, rule_ref) for known renames, else None."""
    return _RENAME_GUESSES.get(column_name)
```

- [ ] **Step 4: Run tests; verify they pass**

Run:

```bash
uv run pytest tests/test_gen_column_naming_audit_inventory.py -v -k initial_rename
```

Expected: all four pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/gen_column_naming_audit_inventory.py \
        tests/test_gen_column_naming_audit_inventory.py
git commit -m "feat(scripts): add _initial_rename_guess helper

Pre-populates proposed_name + rule_ref for the high-confidence subset of
renames from the original #3643 audit. Reviewers accept/override per row.
Tracked on #3643."
```

---

## Task 6: `_structural_additions` — pre-populated new-column rows

**Purpose:** The audit CSV must include rows for the new columns the spec adds
to `dim_students` (MDCPS ID, Salesforce contact ID) and `dim_staff` (Microsoft
365 email). These don't exist in any YAML yet, so the script synthesizes them.

**Files:**

- Modify: `scripts/gen_column_naming_audit_inventory.py`
- Modify: `tests/test_gen_column_naming_audit_inventory.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_gen_column_naming_audit_inventory.py`:

```python
def test_structural_additions_includes_mdcps() -> None:
    module = _load_script()
    rows = module._structural_additions()
    matches = [r for r in rows if r["proposed_name"] == "mdcps_student_identifier"]
    assert len(matches) == 1
    row = matches[0]
    assert row["domain"] == "Student"
    assert row["model"] == "dim_students"
    assert row["action"] == "add"
    assert row["rule_ref"] == "structural"
    assert row["current_column"] == ""
    assert row["review_status"] == "not_reviewed"


def test_structural_additions_includes_salesforce() -> None:
    module = _load_script()
    rows = module._structural_additions()
    assert any(
        r["proposed_name"] == "salesforce_contact_id" and r["model"] == "dim_students"
        for r in rows
    )


def test_structural_additions_includes_microsoft_365_email() -> None:
    module = _load_script()
    rows = module._structural_additions()
    assert any(
        r["proposed_name"] == "microsoft_365_email" and r["model"] == "dim_staff"
        for r in rows
    )


def test_structural_additions_all_have_required_keys() -> None:
    module = _load_script()
    required = {
        "domain",
        "model",
        "current_column",
        "data_type",
        "current_description",
        "action",
        "proposed_name",
        "rule_ref",
        "review_status",
        "reviewer_notes",
    }
    for row in module._structural_additions():
        assert set(row.keys()) == required, f"keys differ for {row}"
```

- [ ] **Step 2: Run tests; verify they fail**

Run:

```bash
uv run pytest tests/test_gen_column_naming_audit_inventory.py -v -k structural
```

Expected: all four fail with `AttributeError`.

- [ ] **Step 3: Implement `_structural_additions`**

Add to `scripts/gen_column_naming_audit_inventory.py`:

```python
def _structural_additions() -> list[dict[str, str]]:
    """Pre-populated add-rows for structural columns defined in the spec."""
    template = {
        "current_column": "",
        "current_description": "",
        "action": "add",
        "rule_ref": "structural",
        "review_status": "not_reviewed",
        "reviewer_notes": "",
    }
    return [
        {
            **template,
            "domain": "Student",
            "model": "dim_students",
            "data_type": "string",
            "proposed_name": "mdcps_student_identifier",
        },
        {
            **template,
            "domain": "Student",
            "model": "dim_students",
            "data_type": "string",
            "proposed_name": "salesforce_contact_id",
        },
        {
            **template,
            "domain": "Staff",
            "model": "dim_staff",
            "data_type": "string",
            "proposed_name": "microsoft_365_email",
        },
    ]
```

- [ ] **Step 4: Run tests; verify they pass**

Run:

```bash
uv run pytest tests/test_gen_column_naming_audit_inventory.py -v -k structural
```

Expected: all four pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/gen_column_naming_audit_inventory.py \
        tests/test_gen_column_naming_audit_inventory.py
git commit -m "feat(scripts): add _structural_additions helper

Pre-populates audit rows for new columns the spec adds to dim_students
(mdcps_student_identifier, salesforce_contact_id) and dim_staff
(microsoft_365_email).
Tracked on #3643."
```

---

## Task 7: `_read_mart_yaml` — parse one YAML file into CSV row dicts

**Purpose:** Read a single dbt properties YAML, iterate its `models[].columns[]`
entries, and emit a list of dicts in the target CSV schema. Initial guesses
(rename / remove / keep) are applied here.

**Files:**

- Modify: `scripts/gen_column_naming_audit_inventory.py`
- Modify: `tests/test_gen_column_naming_audit_inventory.py`
- Create: `tests/fixtures/mart_yaml/dim_sample.yml`

- [ ] **Step 1: Create the YAML fixture**

Write to `tests/fixtures/mart_yaml/dim_sample.yml`:

```yaml
models:
  - name: dim_sample
    description: A fixture model used in unit tests.
    columns:
      - name: sample_key
        data_type: string
        description: >-
          Surrogate key for sample. Spanning multiple lines.
      - name: student_number
        data_type: int64
        description: Local student ID from PowerSchool.
      - name: _dbt_source_relation
        data_type: string
        description: dbt union metadata.
      - name: ordinary_column
        data_type: string
        description: Nothing special.
```

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_gen_column_naming_audit_inventory.py`:

```python
_FIXTURE = _REPO_ROOT / "tests" / "fixtures" / "mart_yaml" / "dim_sample.yml"


def test_read_mart_yaml_emits_one_row_per_column() -> None:
    module = _load_script()
    rows = module._read_mart_yaml(_FIXTURE)
    assert len(rows) == 4


def test_read_mart_yaml_sets_model_and_domain() -> None:
    module = _load_script()
    rows = module._read_mart_yaml(_FIXTURE)
    assert all(r["model"] == "dim_sample" for r in rows)
    # dim_sample is unknown — falls through to Uncategorized
    assert all(r["domain"] == "Uncategorized" for r in rows)


def test_read_mart_yaml_flattens_description() -> None:
    module = _load_script()
    rows = module._read_mart_yaml(_FIXTURE)
    by_name = {r["current_column"]: r for r in rows}
    assert by_name["sample_key"]["current_description"] == (
        "Surrogate key for sample. Spanning multiple lines."
    )


def test_read_mart_yaml_applies_plumbing_default() -> None:
    module = _load_script()
    rows = module._read_mart_yaml(_FIXTURE)
    by_name = {r["current_column"]: r for r in rows}
    plumb = by_name["_dbt_source_relation"]
    assert plumb["action"] == "remove"
    assert plumb["rule_ref"] == "plumbing"
    assert plumb["proposed_name"] == ""


def test_read_mart_yaml_applies_rename_guess() -> None:
    module = _load_script()
    rows = module._read_mart_yaml(_FIXTURE)
    by_name = {r["current_column"]: r for r in rows}
    sn = by_name["student_number"]
    assert sn["action"] == "rename"
    assert sn["proposed_name"] == "local_student_identifier"
    assert sn["rule_ref"] == "R1"


def test_read_mart_yaml_default_is_keep() -> None:
    module = _load_script()
    rows = module._read_mart_yaml(_FIXTURE)
    by_name = {r["current_column"]: r for r in rows}
    ord_row = by_name["ordinary_column"]
    assert ord_row["action"] == "keep"
    assert ord_row["proposed_name"] == ""
    assert ord_row["rule_ref"] == ""


def test_read_mart_yaml_review_status_not_reviewed() -> None:
    module = _load_script()
    rows = module._read_mart_yaml(_FIXTURE)
    assert all(r["review_status"] == "not_reviewed" for r in rows)
    assert all(r["reviewer_notes"] == "" for r in rows)
```

- [ ] **Step 3: Run tests; verify they fail**

Run:

```bash
uv run pytest tests/test_gen_column_naming_audit_inventory.py -v -k read_mart_yaml
```

Expected: all seven fail with `AttributeError`.

- [ ] **Step 4: Implement `_read_mart_yaml`**

Add to `scripts/gen_column_naming_audit_inventory.py` near the top of the file
(after `from __future__ import ...`):

```python
from pathlib import Path

import yaml
```

Then add the function near the bottom, above `main()`:

```python
def _read_mart_yaml(path: Path) -> list[dict[str, str]]:
    """Parse a single mart properties YAML into audit-row dicts."""
    with path.open(encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)

    plumbing = _plumbing_columns()
    rows: list[dict[str, str]] = []

    for model in doc.get("models", []) or []:
        model_name = model["name"]
        domain = _domain_for_model(model_name)
        for column in model.get("columns", []) or []:
            col_name = column["name"]
            row: dict[str, str] = {
                "domain": domain,
                "model": model_name,
                "current_column": col_name,
                "data_type": column.get("data_type", "") or "",
                "current_description": _flatten_description(
                    column.get("description")
                ),
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
                guess = _initial_rename_guess(col_name)
                if guess is not None:
                    proposed, rule_ref = guess
                    row["action"] = "rename"
                    row["proposed_name"] = proposed
                    row["rule_ref"] = rule_ref

            rows.append(row)

    return rows
```

- [ ] **Step 5: Run tests; verify they pass**

Run:

```bash
uv run pytest tests/test_gen_column_naming_audit_inventory.py -v -k read_mart_yaml
```

Expected: all seven pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/gen_column_naming_audit_inventory.py \
        tests/test_gen_column_naming_audit_inventory.py \
        tests/fixtures/mart_yaml/dim_sample.yml
git commit -m "feat(scripts): add _read_mart_yaml parser

Parses one dbt properties YAML into audit-row dicts, applying plumbing and
rename-guess defaults. Covered by fixture-based unit tests.
Tracked on #3643."
```

---

## Task 8: `main()` — orchestrate directory walk + CSV emission

**Purpose:** Walk the three mart properties directories, read every YAML, append
structural-addition rows, sort deterministically, and write the output CSV. This
is the top-level entry point.

**Files:**

- Modify: `scripts/gen_column_naming_audit_inventory.py`
- Modify: `tests/test_gen_column_naming_audit_inventory.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_gen_column_naming_audit_inventory.py`:

```python
import csv
import io


def test_write_csv_emits_header_and_rows() -> None:
    module = _load_script()
    rows = [
        {
            "domain": "Student",
            "model": "dim_students",
            "current_column": "student_number",
            "data_type": "int64",
            "current_description": "Local student ID.",
            "action": "rename",
            "proposed_name": "local_student_identifier",
            "rule_ref": "R1",
            "review_status": "not_reviewed",
            "reviewer_notes": "",
        }
    ]
    buf = io.StringIO()
    module._write_csv(rows, buf)
    buf.seek(0)
    reader = csv.DictReader(buf)
    header = reader.fieldnames
    assert header == [
        "domain",
        "model",
        "current_column",
        "data_type",
        "current_description",
        "action",
        "proposed_name",
        "rule_ref",
        "review_status",
        "reviewer_notes",
    ]
    parsed = list(reader)
    assert len(parsed) == 1
    assert parsed[0]["proposed_name"] == "local_student_identifier"


def test_sort_rows_groups_by_domain_then_model() -> None:
    module = _load_script()
    unsorted = [
        {"domain": "Staff", "model": "dim_staff", "current_column": "a"},
        {"domain": "Student", "model": "dim_students", "current_column": "b"},
        {"domain": "Student", "model": "dim_students", "current_column": "a"},
        {"domain": "Conformed", "model": "dim_dates", "current_column": "c"},
    ]
    out = module._sort_rows(unsorted)
    assert [r["domain"] for r in out] == ["Conformed", "Staff", "Student", "Student"]
    # Within a model, preserve column order from the YAML (stable sort).
    student_rows = [r for r in out if r["domain"] == "Student"]
    assert [r["current_column"] for r in student_rows] == ["b", "a"]
```

- [ ] **Step 2: Run tests; verify they fail**

Run:

```bash
uv run pytest tests/test_gen_column_naming_audit_inventory.py -v -k "write_csv or sort_rows"
```

Expected: both fail with `AttributeError`.

- [ ] **Step 3: Implement `_write_csv`, `_sort_rows`, and fill in `main()`**

Replace the `main()` stub and add helpers in
`scripts/gen_column_naming_audit_inventory.py`:

```python
import csv
from typing import TextIO

CSV_FIELDS: tuple[str, ...] = (
    "domain",
    "model",
    "current_column",
    "data_type",
    "current_description",
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

OUTPUT_CSV = Path(
    "docs/superpowers/specs/2026-04-15-column-naming-audit-inventory.csv"
)


def _sort_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Stable sort by (domain, model). Within a model, YAML order is kept."""
    return sorted(rows, key=lambda r: (r["domain"], r["model"]))


def _write_csv(rows: list[dict[str, str]], fh: TextIO) -> None:
    writer = csv.DictWriter(fh, fieldnames=list(CSV_FIELDS))
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in CSV_FIELDS})


def main() -> None:
    rows: list[dict[str, str]] = []
    for directory in MART_YAML_DIRS:
        for yaml_path in sorted(directory.glob("*.yml")):
            rows.extend(_read_mart_yaml(yaml_path))
    rows.extend(_structural_additions())
    sorted_rows = _sort_rows(rows)

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        _write_csv(sorted_rows, fh)

    print(f"Wrote {len(sorted_rows)} rows to {OUTPUT_CSV}")
```

- [ ] **Step 4: Run tests; verify they pass**

Run:

```bash
uv run pytest tests/test_gen_column_naming_audit_inventory.py -v
```

Expected: **all tests pass** (the pre-existing tests plus the two new ones).

- [ ] **Step 5: Commit**

```bash
git add scripts/gen_column_naming_audit_inventory.py \
        tests/test_gen_column_naming_audit_inventory.py
git commit -m "feat(scripts): implement main() with sort + CSV writing

Walks the three mart properties directories, reads every YAML, appends
structural-addition rows, sorts by (domain, model), and writes the audit
inventory CSV.
Tracked on #3643."
```

---

## Task 9: Execute the script and commit the initial inventory CSV

**Purpose:** Run the script end-to-end against the real mart YAMLs to produce
the first inventory CSV. Verify row count, header, and a few known rows; commit
the output as a reviewable artifact.

**Files:**

- Create: `docs/superpowers/specs/2026-04-15-column-naming-audit-inventory.csv`

- [ ] **Step 1: Run the script**

Run:

```bash
uv run scripts/gen_column_naming_audit_inventory.py
```

Expected output (approximate):
`Wrote 600+ rows to docs/superpowers/specs/2026-04-15-column-naming-audit-inventory.csv`
(exact count depends on current mart YAML contents).

- [ ] **Step 2: Sanity-check the output**

Run:

```bash
head -1 docs/superpowers/specs/2026-04-15-column-naming-audit-inventory.csv
wc -l docs/superpowers/specs/2026-04-15-column-naming-audit-inventory.csv
```

Expected: header exactly
`domain,model,current_column,data_type,current_description,action,proposed_name,rule_ref,review_status,reviewer_notes`.
Line count: header + all column rows + 3 structural additions.

Spot check: confirm three known rows exist in the output.

```bash
grep '^Student,dim_students,student_key,' \
  docs/superpowers/specs/2026-04-15-column-naming-audit-inventory.csv

grep ',mdcps_student_identifier,structural,' \
  docs/superpowers/specs/2026-04-15-column-naming-audit-inventory.csv

grep ',_dbt_source_relation,.*,remove,,plumbing,' \
  docs/superpowers/specs/2026-04-15-column-naming-audit-inventory.csv
```

Each should return at least one line.

- [ ] **Step 3: Commit the inventory CSV**

```bash
git add docs/superpowers/specs/2026-04-15-column-naming-audit-inventory.csv
git commit -m "docs(dbt): generate initial column naming audit inventory

Output of \`uv run scripts/gen_column_naming_audit_inventory.py\` against
the current kipptaf mart YAML state. Ready for import into a Google Sheet
for reviewer annotation.
Tracked on #3643."
```

---

## Task 10: Update `scripts/CLAUDE.md` catalog

**Purpose:** Document the new script in the `scripts/` catalog so it's
discoverable.

**Files:**

- Modify: `scripts/CLAUDE.md:8-22`

- [ ] **Step 1: Edit the catalog table**

In `scripts/CLAUDE.md`, insert a new row in the catalog table (the table at
lines 8–22) in alphabetical position between `gen-automations-doc.py` and
`init_sftp_integration.py`:

Use the Edit tool with:

- `old_string`:

  ```text
  | `gen-automations-doc.py`                      | Regenerate `docs/reference/automations.md`          |
  | `init_sftp_integration.py`                    | Inspect SFTP servers and scaffold new integrations  |
  ```

- `new_string`:

  ```text
  | `gen-automations-doc.py`                      | Regenerate `docs/reference/automations.md`          |
  | `gen_column_naming_audit_inventory.py`        | Generate mart column naming audit inventory CSV     |
  | `init_sftp_integration.py`                    | Inspect SFTP servers and scaffold new integrations  |
  ```

- [ ] **Step 2: Commit**

```bash
git add scripts/CLAUDE.md
git commit -m "docs(scripts): catalog gen_column_naming_audit_inventory

Tracked on #3643."
```

---

## Post-plan handoff

After Task 10, the worktree contains:

- A tested inventory-generation script
  (`scripts/gen_column_naming_audit_inventory.py`).
- Unit tests under `tests/test_gen_column_naming_audit_inventory.py` plus a YAML
  fixture.
- The initial CSV inventory at
  `docs/superpowers/specs/2026-04-15-column-naming-audit-inventory.csv`.
- Scripts catalog updated.

### Next manual step (human-gated)

1. Create a Google Sheet, import the CSV, share with the audit-review team.
2. Post the sheet URL to issue
   [#3643](https://github.com/TEAMSchools/teamster/issues/3643) and add it to
   the `Sheet URL` placeholder in the spec.
3. Reviewers annotate `review_status`, `proposed_name`, and `reviewer_notes` in
   the sheet.
4. When all rows reach `approved`, export the sheet back to CSV and commit as
   `docs/superpowers/specs/2026-04-15-column-naming-audit-approved.csv`.

### Follow-up plan

Once the approved CSV lands, a separate implementation plan covers:

- Building the script that reads the approved CSV and emits SQL + YAML edits.
- Structural additions: upstream dbt work in staging/intermediate layers to
  populate the new `dim_students` and `dim_staff` columns.
- Running the implementation script, generating the single PR for the refactor.

That plan is written during the second writing-plans pass, after reviewers
complete their annotation and we have concrete approved-row decisions to drive
the implementation.

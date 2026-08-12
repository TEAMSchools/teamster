# Quill Pilot Demographics Extract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a rerunnable script that turns the Quill pilot roster into a
de-identified demographics workbook for an external research partner, plus the
documentation the data sharing agreement requires.

**Architecture:** One script under `scripts/`, structured as pure functions
(label maps, code assignment, row building, whitelist validation) wrapped by
thin I/O edges (roster read, BigQuery fetch, workbook write, key file). The pure
core carries the unit tests; the I/O edges are verified by a real run against
the actual roster. Nothing about the roster is hardcoded — paths are arguments,
so no student data enters git.

**Tech Stack:** Python 3.13, `uv run`, and pytest. `openpyxl` and
`google-cloud-bigquery` are declared in a PEP 723 inline metadata header rather
than in `pyproject.toml`, following `scripts/extract_ceds_schema.py`.

Design spec:
`docs/superpowers/specs/2026-08-12-quill-seta-ed-demographics-design.md`. Issue:
#4848.

## Global Constraints

- **Worktree:**
  `/workspaces/teamster/.worktrees/anthonygwalters/feat/claude-quill-seta-demographics`.
  Every `git` command uses `git -C {worktree}`. Every file path below is
  relative to that worktree. Editing `/workspaces/teamster/{path}` instead
  silently dirties `main` and leaves the worktree unchanged.
- **Python invocation:** always `uv run`, never bare `python`. Neither
  `openpyxl` nor `google-cloud-bigquery` is a direct `pyproject.toml`
  dependency, and neither gets added — the script declares them in a PEP 723
  inline metadata header, matching `scripts/extract_ceds_schema.py`, so
  `uv run scripts/extract_quill_seta_ed_demographics.py ...` resolves them at
  launch with no flags. Do not run `uv add`.
- **Tests still need the flag.** pytest loads the script through `importlib`,
  which ignores PEP 723, so every test command is
  `uv run --with openpyxl pytest ...`. Without it the openpyxl-dependent tests
  SKIP rather than fail — a silent pass is the failure mode to watch for.
- **Pyright runs over `scripts/` and `tests/` in CI.** `openpyxl` ships stubs
  but no installed source, so each `import openpyxl` needs
  `# trunk-ignore(pyright/reportMissingModuleSource): openpyxl is a PEP 723 script dep`
  on the line immediately before it — the exact form used in
  `scripts/extract_ceds_schema.py`.
- **Do not annotate test helpers with a type from the loaded module**
  (`-> list[mod.RosterRow]`): `mod` is a runtime variable, so pyright raises
  `reportInvalidTypeForm`. Use a bare `-> list`. (`scripts/CLAUDE.md`.)
- **IDE Pyright diagnostics on worktree files are false positives** (it resolves
  imports against the main checkout). Trust `uv run` inside the worktree.
- **No PII in git.** No student name, student email, teacher name, teacher
  email, `student_number`, or roster path with real data may appear in any
  committed file — script, test, fixture, docs, or commit message. Test fixtures
  use invented names.
- **No PII outside the repo.** Nothing in this plan writes to GitHub, Slack,
  Asana, or any external surface. The workbook and the key file are local
  artifacts only.
- **Source of truth:**
  `teamster-332318.kipptaf_extracts.int_extracts__student_enrollments`.
- **Pilot year:** `academic_year = 2025` (SY25-26), overridable by flag.
- **Read-only warehouse access.** The script issues one `SELECT`. No DML, no
  DDL, no table creation.
- **Lint:** `trunk fmt` runs at commit. Before any push, run
  `cd {worktree} && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix {files} </dev/null`.
- **Tests are local only** — CI runs Trunk, not pytest. Run tests yourself; do
  not assume CI catches a failure.

---

## File Structure

| Path                                                   | Responsibility                                                                                                                    |
| ------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------- |
| `scripts/extract_quill_seta_ed_demographics.py`        | Everything: pure transforms plus I/O edges. Single file, matching the existing `scripts/` convention.                             |
| `tests/test_extract_quill_seta_ed_demographics.py`     | Unit tests for the pure core and the roster reader. Imports the script by path, mirroring `tests/test_extract_pdf_dictionary.py`. |
| `docs/reference/quill-seta-ed-demographics-extract.md` | Data dictionary, lineage, inclusion and exclusion rules, rerun steps.                                                             |
| `mkdocs.yml`                                           | One nav entry under `Reference`.                                                                                                  |
| `scripts/CLAUDE.md`                                    | One catalog row.                                                                                                                  |

Task 1 builds the pure core. Task 2 adds the roster reader and key file. Task 3
adds the workbook writer. Task 4 adds the BigQuery query and `main()`, and
produces the real deliverable. Task 5 is documentation.

---

### Task 1: Pure core — labels, codes, rows, validation

**Files:**

- Create: `scripts/extract_quill_seta_ed_demographics.py`
- Test: `tests/test_extract_quill_seta_ed_demographics.py`

**Interfaces:**

- Consumes: nothing.
- Produces, for later tasks:
  - `RosterRow` dataclass: `quill_student_id: int`, `student_email: str`,
    `classroom_name: str`, `teacher_name: str`
  - `Demographics` dataclass: `academic_year: int`, `student_number: int`,
    `race_ethnicity: str`, `gender: str`, `meal_status: str`, `iep_status: str`,
    `mll_status: str`
  - `OUTPUT_COLUMNS: tuple[str, ...]`
  - `school_year_label(academic_year: int) -> str`
  - `label_race(code: str | None) -> str`
  - `label_gender(code: str | None) -> str`
  - `label_meal(code: str | None) -> str`
  - `assign_codes(names, existing, prefix, width) -> dict[str, str]`
  - `build_output_rows(roster, demographics, pilot_year, classroom_codes, teacher_codes) -> list[dict[str, object]]`
  - `build_key_records(roster, demographics, classroom_codes, teacher_codes) -> list[dict[str, object]]`
  - `validate_rows(rows, roster) -> None`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_extract_quill_seta_ed_demographics.py`:

```python
"""Unit tests for scripts/extract_quill_seta_ed_demographics.py.

The script filename uses underscores specifically so we can import it.
We use importlib.util rather than changing project-wide pytest config,
keeping the import pattern local to this test file.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO_ROOT / "scripts" / "extract_quill_seta_ed_demographics.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "extract_quill_seta_ed_demographics", _SCRIPT
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before executing: @dataclass resolves string annotations via
    # sys.modules.get(cls.__module__).__dict__, which is an unguarded None
    # dereference in CPython 3.13 when the module was never registered.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script() -> ModuleType:
    return _load_script()


def _roster(module: ModuleType) -> list:
    """Four invented students across two classrooms and two teachers."""
    return [
        module.RosterRow(1001, "aaa@example.org", "Room Alpha", "Teacher One"),
        module.RosterRow(1002, "bbb@example.org", "Room Beta", "Teacher Two"),
        module.RosterRow(1003, "ccc@example.org", "Room Alpha", "Teacher One"),
        # 1001 again, second section of the same teacher
        module.RosterRow(1001, "aaa@example.org", "Room Beta", "Teacher Two"),
    ]


class TestSchoolYearLabel:
    def test_pilot_year(self, script: ModuleType) -> None:
        assert script.school_year_label(2025) == "SY25-26"

    def test_prior_year(self, script: ModuleType) -> None:
        assert script.school_year_label(2024) == "SY24-25"

    def test_century_rollover(self, script: ModuleType) -> None:
        assert script.school_year_label(2099) == "SY99-00"


class TestLabelRace:
    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            ("A", "Asian"),
            ("B", "BL-AA"),
            ("H", "Hispanic or Latino"),
            ("I", "AI-AN"),
            ("P", "NH-OPI"),
            ("T", "2+ races"),
            ("W", "White"),
            ("M", "DTS"),
            ("N", "DTS"),
            ("Y", "DTS"),
        ],
    )
    def test_known_codes(
        self, script: ModuleType, code: str, expected: str
    ) -> None:
        assert script.label_race(code) == expected

    def test_unknown_code_falls_back(self, script: ModuleType) -> None:
        assert script.label_race("Z") == "DTS"

    def test_none_is_empty(self, script: ModuleType) -> None:
        assert script.label_race(None) == ""


class TestLabelGender:
    @pytest.mark.parametrize(
        ("code", "expected"),
        [("F", "Female"), ("M", "Male"), ("X", "Non-Binary")],
    )
    def test_known_codes(
        self, script: ModuleType, code: str, expected: str
    ) -> None:
        assert script.label_gender(code) == expected

    def test_none_is_empty(self, script: ModuleType) -> None:
        assert script.label_gender(None) == ""

    def test_unknown_code_is_empty(self, script: ModuleType) -> None:
        assert script.label_gender("Q") == ""


class TestLabelMeal:
    @pytest.mark.parametrize(
        ("code", "expected"),
        [("F", "Free"), ("FDC", "Free"), ("R", "Reduced"), ("P", "Paid")],
    )
    def test_known_codes(
        self, script: ModuleType, code: str, expected: str
    ) -> None:
        assert script.label_meal(code) == expected

    def test_lowercase_code(self, script: ModuleType) -> None:
        assert script.label_meal("f") == "Free"

    def test_none_is_empty(self, script: ModuleType) -> None:
        assert script.label_meal(None) == ""


class TestAssignCodes:
    def test_first_appearance_order(self, script: ModuleType) -> None:
        names = ["Zeta", "Alpha", "Zeta", "Mu"]
        assert script.assign_codes(names, {}, "C", 2) == {
            "Zeta": "C01",
            "Alpha": "C02",
            "Mu": "C03",
        }

    def test_is_not_alphabetical(self, script: ModuleType) -> None:
        """Alphabetical assignment would be publicly derivable. It must not be."""
        assert script.assign_codes(["Zeta", "Alpha"], {}, "C", 2)["Zeta"] == "C01"

    def test_existing_assignments_are_reused(self, script: ModuleType) -> None:
        existing = {"Alpha": "C07"}
        result = script.assign_codes(["Zeta", "Alpha"], existing, "C", 2)
        assert result == {"Alpha": "C07", "Zeta": "C08"}

    def test_width_one(self, script: ModuleType) -> None:
        assert script.assign_codes(["One", "Two"], {}, "T", 1) == {
            "One": "T1",
            "Two": "T2",
        }


class TestBuildOutputRows:
    def test_row_count_matches_roster(self, script: ModuleType) -> None:
        roster = _roster(script)
        rows = script.build_output_rows(roster, {}, 2025, {}, {})
        assert len(rows) == len(roster)

    def test_pilot_year_row(self, script: ModuleType) -> None:
        roster = _roster(script)
        demographics = {
            "aaa@example.org": script.Demographics(
                2025, 900001, "B", "F", "F", "Has IEP", "Not ML"
            )
        }
        rows = script.build_output_rows(
            roster,
            demographics,
            2025,
            {"Room Alpha": "C01", "Room Beta": "C02"},
            {"Teacher One": "T1", "Teacher Two": "T2"},
        )
        assert rows[0] == {
            "quill_student_id": 1001,
            "classroom_code": "C01",
            "teacher_code": "T1",
            "race_ethnicity": "BL-AA",
            "gender": "Female",
            "meal_status": "Free",
            "iep_status": "Has IEP",
            "mll_status": "Not ML",
            "demographics_source": "SY25-26",
        }

    def test_fallback_year_is_flagged(self, script: ModuleType) -> None:
        roster = _roster(script)
        demographics = {
            "bbb@example.org": script.Demographics(
                2024, 900002, "H", "M", "R", "No IEP", "ML"
            )
        }
        rows = script.build_output_rows(roster, demographics, 2025, {}, {})
        assert rows[1]["demographics_source"] == "SY24-25 (fallback)"
        assert rows[1]["race_ethnicity"] == "Hispanic or Latino"

    def test_unmatched_student_is_blank_and_flagged(
        self, script: ModuleType
    ) -> None:
        rows = script.build_output_rows(_roster(script), {}, 2025, {}, {})
        assert rows[2]["demographics_source"] == "not matched"
        assert rows[2]["race_ethnicity"] == ""
        assert rows[2]["gender"] == ""
        assert rows[2]["meal_status"] == ""
        assert rows[2]["iep_status"] == ""
        assert rows[2]["mll_status"] == ""

    def test_duplicate_student_gets_both_classrooms(
        self, script: ModuleType
    ) -> None:
        rows = script.build_output_rows(
            _roster(script),
            {},
            2025,
            {"Room Alpha": "C01", "Room Beta": "C02"},
            {},
        )
        first = [r for r in rows if r["quill_student_id"] == 1001]
        assert [r["classroom_code"] for r in first] == ["C01", "C02"]

    def test_no_name_or_email_in_any_row(self, script: ModuleType) -> None:
        rows = script.build_output_rows(_roster(script), {}, 2025, {}, {})
        flat = " ".join(str(v) for row in rows for v in row.values())
        assert "@" not in flat
        assert "Teacher" not in flat
        assert "Room" not in flat

    def test_columns_are_exactly_output_columns(
        self, script: ModuleType
    ) -> None:
        rows = script.build_output_rows(_roster(script), {}, 2025, {}, {})
        for row in rows:
            assert tuple(row) == script.OUTPUT_COLUMNS


class TestBuildKeyRecords:
    def test_key_retains_the_identifiers_the_workbook_drops(
        self, script: ModuleType
    ) -> None:
        demographics = {
            "aaa@example.org": script.Demographics(
                2025, 900001, "B", "F", "F", "No IEP", "Not ML"
            )
        }
        records = script.build_key_records(
            _roster(script),
            demographics,
            {"Room Alpha": "C01", "Room Beta": "C02"},
            {"Teacher One": "T1", "Teacher Two": "T2"},
        )
        assert records[0] == {
            "quill_student_id": 1001,
            "student_email": "aaa@example.org",
            "student_number": 900001,
            "classroom_name": "Room Alpha",
            "teacher_name": "Teacher One",
            "classroom_code": "C01",
            "teacher_code": "T1",
        }

    def test_unmatched_student_has_no_student_number(
        self, script: ModuleType
    ) -> None:
        records = script.build_key_records(_roster(script), {}, {}, {})
        assert records[0]["student_number"] is None


class TestValidateRows:
    def _valid(self, script: ModuleType) -> list[dict]:
        return script.build_output_rows(
            _roster(script),
            {
                "aaa@example.org": script.Demographics(
                    2025, 900001, "B", "F", "F", "No IEP", "Not ML"
                )
            },
            2025,
            {"Room Alpha": "C01", "Room Beta": "C02"},
            {"Teacher One": "T1", "Teacher Two": "T2"},
        )

    def test_valid_rows_pass(self, script: ModuleType) -> None:
        script.validate_rows(self._valid(script), _roster(script))

    def test_row_count_mismatch_raises(self, script: ModuleType) -> None:
        rows = self._valid(script)[:-1]
        with pytest.raises(ValueError, match="row count"):
            script.validate_rows(rows, _roster(script))

    def test_unexpected_quill_id_raises(self, script: ModuleType) -> None:
        rows = self._valid(script)
        rows[0]["quill_student_id"] = 999999
        with pytest.raises(ValueError, match="quill_student_id"):
            script.validate_rows(rows, _roster(script))

    def test_email_shaped_value_raises(self, script: ModuleType) -> None:
        rows = self._valid(script)
        rows[0]["race_ethnicity"] = "aaa@example.org"
        with pytest.raises(ValueError, match="disallowed value"):
            script.validate_rows(rows, _roster(script))

    def test_name_leaking_into_a_cell_raises(self, script: ModuleType) -> None:
        rows = self._valid(script)
        rows[0]["classroom_code"] = "Room Alpha"
        with pytest.raises(ValueError, match="classroom_code"):
            script.validate_rows(rows, _roster(script))

    def test_off_vocabulary_label_raises(self, script: ModuleType) -> None:
        rows = self._valid(script)
        rows[0]["gender"] = "F"
        with pytest.raises(ValueError, match="disallowed value"):
            script.validate_rows(rows, _roster(script))

    def test_unknown_source_raises(self, script: ModuleType) -> None:
        rows = self._valid(script)
        rows[0]["demographics_source"] = "whenever"
        with pytest.raises(ValueError, match="demographics_source"):
            script.validate_rows(rows, _roster(script))
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-quill-seta-demographics
uv run pytest tests/test_extract_quill_seta_ed_demographics.py -v
```

Expected: collection error — `scripts/extract_quill_seta_ed_demographics.py`
does not exist yet.

- [ ] **Step 3: Write the pure core**

Create `scripts/extract_quill_seta_ed_demographics.py`:

```python
# /// script
# requires-python = ">=3.13"
# dependencies = ["openpyxl>=3.1", "google-cloud-bigquery>=3.0"]
# ///

"""Build a de-identified demographics workbook for the Quill pilot roster.

The roster export keys students by Quill's own platform user ID, not by any
KIPP identifier, so the delivered workbook carries no KIPP identifier at all.
The mapping back to real students is written to a separate local key file that
is never committed and never transmitted.

See docs/reference/quill-seta-ed-demographics-extract.md.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

OUTPUT_COLUMNS: tuple[str, ...] = (
    "quill_student_id",
    "classroom_code",
    "teacher_code",
    "race_ethnicity",
    "gender",
    "meal_status",
    "iep_status",
    "mll_status",
    "demographics_source",
)

# Mirrors rpt_gsheets__csgf_enrollment so the network keeps one convention.
RACE_LABELS: dict[str, str] = {
    "A": "Asian",
    "B": "BL-AA",
    "H": "Hispanic or Latino",
    "I": "AI-AN",
    "M": "DTS",
    "N": "DTS",
    "P": "NH-OPI",
    "T": "2+ races",
    "W": "White",
    "Y": "DTS",
}
UNKNOWN_RACE = "DTS"

GENDER_LABELS: dict[str, str] = {"F": "Female", "M": "Male", "X": "Non-Binary"}

MEAL_LABELS: dict[str, str] = {
    "F": "Free",
    "FDC": "Free",
    "R": "Reduced",
    "P": "Paid",
}

IEP_LABELS: frozenset[str] = frozenset({"Has IEP", "No IEP"})
MLL_LABELS: frozenset[str] = frozenset({"ML", "Not ML"})

NOT_MATCHED = "not matched"
_SOURCE_PATTERN = re.compile(r"^SY\d{2}-\d{2}( \(fallback\))?$")
_CLASSROOM_CODE_PATTERN = re.compile(r"^C\d{2}$")
_TEACHER_CODE_PATTERN = re.compile(r"^T\d+$")


@dataclass(frozen=True)
class RosterRow:
    """One student-classroom pair as exported from the Quill platform."""

    quill_student_id: int
    student_email: str
    classroom_name: str
    teacher_name: str


@dataclass(frozen=True)
class Demographics:
    """One student's warehouse record for a single academic year."""

    academic_year: int
    student_number: int
    race_ethnicity: str
    gender: str
    meal_status: str
    iep_status: str
    mll_status: str


def school_year_label(academic_year: int) -> str:
    """2025 -> 'SY25-26'."""
    return f"SY{academic_year % 100:02d}-{(academic_year + 1) % 100:02d}"


def label_race(code: str | None) -> str:
    if code is None or code == "":
        return ""
    return RACE_LABELS.get(code.strip().upper(), UNKNOWN_RACE)


def label_gender(code: str | None) -> str:
    if code is None or code == "":
        return ""
    return GENDER_LABELS.get(code.strip().upper(), "")


def label_meal(code: str | None) -> str:
    if code is None or code == "":
        return ""
    return MEAL_LABELS.get(code.strip().upper(), "")


def assign_codes(
    names: Iterable[str],
    existing: Mapping[str, str],
    prefix: str,
    width: int,
) -> dict[str, str]:
    """Assign codes in order of first appearance, reusing prior assignments.

    Order of first appearance rather than alphabetical order: this script is
    public, and an alphabetical rule would let anyone who knows the real
    classroom or teacher names derive the mapping.
    """
    codes = dict(existing)
    used = [
        int(code[len(prefix) :])
        for code in codes.values()
        if code[len(prefix) :].isdigit()
    ]
    next_index = max(used, default=0) + 1

    for name in names:
        if name in codes:
            continue

        codes[name] = f"{prefix}{next_index:0{width}d}"
        next_index += 1

    return codes


def build_output_rows(
    roster: Sequence[RosterRow],
    demographics: Mapping[str, Demographics],
    pilot_year: int,
    classroom_codes: Mapping[str, str],
    teacher_codes: Mapping[str, str],
) -> list[dict[str, object]]:
    """One output row per roster row, carrying no identifier but the Quill ID."""
    rows: list[dict[str, object]] = []

    for entry in roster:
        record = demographics.get(entry.student_email)

        if record is None:
            source = NOT_MATCHED
        elif record.academic_year == pilot_year:
            source = school_year_label(record.academic_year)
        else:
            source = f"{school_year_label(record.academic_year)} (fallback)"

        rows.append(
            {
                "quill_student_id": entry.quill_student_id,
                "classroom_code": classroom_codes.get(entry.classroom_name, ""),
                "teacher_code": teacher_codes.get(entry.teacher_name, ""),
                "race_ethnicity": label_race(
                    record.race_ethnicity if record else None
                ),
                "gender": label_gender(record.gender if record else None),
                "meal_status": label_meal(record.meal_status if record else None),
                "iep_status": record.iep_status if record else "",
                "mll_status": record.mll_status if record else "",
                "demographics_source": source,
            }
        )

    return rows


def build_key_records(
    roster: Sequence[RosterRow],
    demographics: Mapping[str, Demographics],
    classroom_codes: Mapping[str, str],
    teacher_codes: Mapping[str, str],
) -> list[dict[str, object]]:
    """The re-identification key the agreement requires the supplier to retain."""
    records: list[dict[str, object]] = []

    for entry in roster:
        record = demographics.get(entry.student_email)

        records.append(
            {
                "quill_student_id": entry.quill_student_id,
                "student_email": entry.student_email,
                "student_number": record.student_number if record else None,
                "classroom_name": entry.classroom_name,
                "teacher_name": entry.teacher_name,
                "classroom_code": classroom_codes.get(entry.classroom_name, ""),
                "teacher_code": teacher_codes.get(entry.teacher_name, ""),
            }
        )

    return records


def validate_rows(
    rows: Sequence[Mapping[str, object]], roster: Sequence[RosterRow]
) -> None:
    """Whitelist every delivered cell. Raises ValueError on the first problem.

    Whitelisting rather than scanning for known names: a blacklist false-fires
    on surnames that collide with labels ('Free', 'Male') and silently misses
    anything not on the list.
    """
    if len(rows) != len(roster):
        raise ValueError(f"row count {len(rows)} does not match roster {len(roster)}")

    allowed_ids = {entry.quill_student_id for entry in roster}
    allowed: dict[str, frozenset[str]] = {
        "race_ethnicity": frozenset(RACE_LABELS.values()) | {""},
        "gender": frozenset(GENDER_LABELS.values()) | {""},
        "meal_status": frozenset(MEAL_LABELS.values()) | {""},
        "iep_status": IEP_LABELS | {""},
        "mll_status": MLL_LABELS | {""},
    }

    for index, row in enumerate(rows):
        if tuple(row) != OUTPUT_COLUMNS:
            raise ValueError(f"row {index} columns are {tuple(row)}")

        if row["quill_student_id"] not in allowed_ids:
            raise ValueError(f"row {index} quill_student_id is not on the roster")

        classroom_code = str(row["classroom_code"])
        if not _CLASSROOM_CODE_PATTERN.match(classroom_code):
            raise ValueError(f"row {index} classroom_code {classroom_code!r} is not a code")

        teacher_code = str(row["teacher_code"])
        if not _TEACHER_CODE_PATTERN.match(teacher_code):
            raise ValueError(f"row {index} teacher_code {teacher_code!r} is not a code")

        for column, vocabulary in allowed.items():
            value = str(row[column])
            if value not in vocabulary:
                raise ValueError(f"row {index} {column} disallowed value {value!r}")

        source = str(row["demographics_source"])
        if source != NOT_MATCHED and not _SOURCE_PATTERN.match(source):
            raise ValueError(f"row {index} demographics_source {source!r}")
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-quill-seta-demographics
uv run pytest tests/test_extract_quill_seta_ed_demographics.py -v
```

Expected: PASS. If `test_name_leaking_into_a_cell_raises` fails, the classroom
code regex is matching a real name — fix the pattern, not the test.

- [ ] **Step 5: Commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-quill-seta-demographics
git add scripts/extract_quill_seta_ed_demographics.py tests/test_extract_quill_seta_ed_demographics.py
git commit -m "feat(scripts): pure core for the Quill pilot demographics extract

Refs #4848"
```

---

### Task 2: Roster reader and key file

**Files:**

- Modify: `scripts/extract_quill_seta_ed_demographics.py`
- Modify: `tests/test_extract_quill_seta_ed_demographics.py`

**Interfaces:**

- Consumes: `RosterRow`, `build_key_records` from Task 1.
- Produces:
  - `ROSTER_HEADERS: tuple[str, ...]` — the exact header row the export ships,
    including the upstream typo `Studetn ID`
  - `read_roster(path: Path) -> list[RosterRow]`
  - `read_codebook(path: Path) -> tuple[dict[str, str], dict[str, str]]`
    returning `(classroom_codes, teacher_codes)`, both empty when the file is
    absent
  - `write_key_file(path, classroom_codes, teacher_codes, key_records) -> None`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_extract_quill_seta_ed_demographics.py`:

```python
class TestReadRoster:
    def _workbook(self, path, rows) -> None:
        openpyxl = pytest.importorskip("openpyxl")
        workbook = openpyxl.Workbook()
        sheet = workbook.worksheets[0]
        sheet.append(
            [
                "Studetn ID",
                "Student Name",
                "Student Email",
                "Classroom Name",
                "Teacher Name",
                "Teacher Email",
            ]
        )
        for row in rows:
            sheet.append(row)
        workbook.save(path)

    def test_reads_every_row(self, script: ModuleType, tmp_path: Path) -> None:
        path = tmp_path / "roster.xlsx"
        self._workbook(
            path,
            [
                [1001, "Ann Ant", "AAA@Example.org", "Room Alpha", "Teacher One", "t1@example.org"],
                [1002, "Bob Bee", "bbb@example.org", "Room Beta", "Teacher Two", "t2@example.org"],
            ],
        )
        roster = script.read_roster(path)
        assert len(roster) == 2
        assert roster[0].quill_student_id == 1001
        assert roster[0].classroom_name == "Room Alpha"
        assert roster[0].teacher_name == "Teacher One"

    def test_email_is_lowercased(self, script: ModuleType, tmp_path: Path) -> None:
        path = tmp_path / "roster.xlsx"
        self._workbook(
            path,
            [[1001, "Ann Ant", "AAA@Example.org", "Room Alpha", "Teacher One", "t1@example.org"]],
        )
        assert script.read_roster(path)[0].student_email == "aaa@example.org"

    def test_blank_trailing_rows_are_skipped(
        self, script: ModuleType, tmp_path: Path
    ) -> None:
        path = tmp_path / "roster.xlsx"
        self._workbook(
            path,
            [
                [1001, "Ann Ant", "aaa@example.org", "Room Alpha", "Teacher One", "t1@example.org"],
                [None, None, None, None, None, None],
            ],
        )
        assert len(script.read_roster(path)) == 1

    def test_unexpected_headers_raise(
        self, script: ModuleType, tmp_path: Path
    ) -> None:
        openpyxl = pytest.importorskip("openpyxl")
        path = tmp_path / "roster.xlsx"
        workbook = openpyxl.Workbook()
        workbook.worksheets[0].append(["Student ID", "Nope"])
        workbook.save(path)
        with pytest.raises(ValueError, match="header"):
            script.read_roster(path)


class TestCodebook:
    def test_missing_file_returns_empty(
        self, script: ModuleType, tmp_path: Path
    ) -> None:
        assert script.read_codebook(tmp_path / "absent.json") == ({}, {})

    def test_round_trip_preserves_codes(
        self, script: ModuleType, tmp_path: Path
    ) -> None:
        path = tmp_path / "key.json"
        script.write_key_file(
            path,
            {"Room Alpha": "C01"},
            {"Teacher One": "T1"},
            [{"quill_student_id": 1001, "student_email": "aaa@example.org"}],
        )
        assert script.read_codebook(path) == (
            {"Room Alpha": "C01"},
            {"Teacher One": "T1"},
        )

    def test_key_file_holds_the_student_records(
        self, script: ModuleType, tmp_path: Path
    ) -> None:
        import json

        path = tmp_path / "key.json"
        script.write_key_file(
            path, {}, {}, [{"quill_student_id": 1001, "student_email": "aaa@example.org"}]
        )
        stored = json.loads(path.read_text())
        assert stored["students"][0]["student_email"] == "aaa@example.org"
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-quill-seta-demographics
uv run --with openpyxl pytest tests/test_extract_quill_seta_ed_demographics.py -k "ReadRoster or Codebook" -v
```

Expected: FAIL with `AttributeError: module ... has no attribute 'read_roster'`.

- [ ] **Step 3: Implement the reader and key file**

Add to the imports at the top of the script:

```python
import json
from pathlib import Path
```

Add after the `validate_rows` function:

```python
ROSTER_HEADERS: tuple[str, ...] = (
    "Studetn ID",  # upstream typo; matched verbatim so a fixed export fails loudly
    "Student Name",
    "Student Email",
    "Classroom Name",
    "Teacher Name",
    "Teacher Email",
)


def read_roster(path: Path) -> list[RosterRow]:
    """Read the Quill roster export, keeping only the columns we carry forward."""
    # trunk-ignore(pyright/reportMissingModuleSource): openpyxl is a PEP 723 script dep
    import openpyxl

    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheet = workbook.worksheets[0]
    rows = sheet.iter_rows(values_only=True)

    header = tuple(str(value) if value is not None else "" for value in next(rows))
    if header[: len(ROSTER_HEADERS)] != ROSTER_HEADERS:
        raise ValueError(f"unexpected roster header {header!r}")

    roster: list[RosterRow] = []
    for row in rows:
        raw_id = row[0]
        if raw_id is None:
            continue

        # openpyxl types a cell as a wide union (formula, datetime, rich text).
        # Narrow before int() so an unexpected ID cell fails loudly here rather
        # than raising something obscure, and so pyright can check the call.
        if not isinstance(raw_id, int | float | str):
            raise ValueError(f"unexpected roster id cell {raw_id!r}")

        roster.append(
            RosterRow(
                quill_student_id=int(raw_id),
                student_email=str(row[2]).strip().lower(),
                classroom_name=str(row[3]).strip(),
                teacher_name=str(row[4]).strip(),
            )
        )

    workbook.close()

    return roster


def read_codebook(path: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Prior code assignments, so a rerun keeps the same codes."""
    if not path.exists():
        return {}, {}

    stored = json.loads(path.read_text())

    return stored.get("classroom_codes", {}), stored.get("teacher_codes", {})


def write_key_file(
    path: Path,
    classroom_codes: Mapping[str, str],
    teacher_codes: Mapping[str, str],
    key_records: Sequence[Mapping[str, object]],
) -> None:
    """Write the retained re-identification key. Local only, never transmitted."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "classroom_codes": dict(classroom_codes),
                "teacher_codes": dict(teacher_codes),
                "students": [dict(record) for record in key_records],
            },
            indent=2,
            sort_keys=True,
        )
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-quill-seta-demographics
uv run --with openpyxl pytest tests/test_extract_quill_seta_ed_demographics.py -v
```

Expected: PASS, all tests including Task 1's.

- [ ] **Step 5: Commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-quill-seta-demographics
git add scripts/extract_quill_seta_ed_demographics.py tests/test_extract_quill_seta_ed_demographics.py
git commit -m "feat(scripts): roster reader and retained key file

Refs #4848"
```

---

### Task 3: Workbook writer

**Files:**

- Modify: `scripts/extract_quill_seta_ed_demographics.py`
- Modify: `tests/test_extract_quill_seta_ed_demographics.py`

**Interfaces:**

- Consumes: `OUTPUT_COLUMNS` from Task 1.
- Produces:
  - `DATA_DICTIONARY: tuple[tuple[str, str, str, str], ...]` — rows of
    `(column, definition, source, coding)`
  - `write_workbook(path: Path, rows: Sequence[Mapping[str, object]]) -> None`
  - `read_workbook_rows(path: Path) -> list[dict[str, object]]` — reads the
    delivered sheet back so Task 4 can validate the written file rather than the
    in-memory rows

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_extract_quill_seta_ed_demographics.py`:

```python
class TestWriteWorkbook:
    def _rows(self, script: ModuleType) -> list[dict]:
        return script.build_output_rows(
            _roster(script),
            {
                "aaa@example.org": script.Demographics(
                    2025, 900001, "B", "F", "F", "No IEP", "Not ML"
                )
            },
            2025,
            {"Room Alpha": "C01", "Room Beta": "C02"},
            {"Teacher One": "T1", "Teacher Two": "T2"},
        )

    def _write(self, script: ModuleType, path: Path) -> None:
        script.write_workbook(path, self._rows(script))

    def test_creates_both_sheets(self, script: ModuleType, tmp_path: Path) -> None:
        openpyxl = pytest.importorskip("openpyxl")
        path = tmp_path / "out.xlsx"
        self._write(script, path)
        workbook = openpyxl.load_workbook(path)
        assert workbook.sheetnames == ["student_demographics", "data_dictionary"]

    def test_header_row_is_output_columns(
        self, script: ModuleType, tmp_path: Path
    ) -> None:
        openpyxl = pytest.importorskip("openpyxl")
        path = tmp_path / "out.xlsx"
        self._write(script, path)
        sheet = openpyxl.load_workbook(path)["student_demographics"]
        header = tuple(cell.value for cell in sheet[1])
        assert header == script.OUTPUT_COLUMNS

    def test_row_count_matches(self, script: ModuleType, tmp_path: Path) -> None:
        openpyxl = pytest.importorskip("openpyxl")
        path = tmp_path / "out.xlsx"
        self._write(script, path)
        sheet = openpyxl.load_workbook(path)["student_demographics"]
        assert sheet.max_row == len(_roster(script)) + 1

    def test_dictionary_documents_every_column(
        self, script: ModuleType, tmp_path: Path
    ) -> None:
        openpyxl = pytest.importorskip("openpyxl")
        path = tmp_path / "out.xlsx"
        self._write(script, path)
        sheet = openpyxl.load_workbook(path)["data_dictionary"]
        documented = {row[0].value for row in sheet.iter_rows(min_row=2)}
        assert documented == set(script.OUTPUT_COLUMNS)

    def test_written_file_contains_no_at_sign(
        self, script: ModuleType, tmp_path: Path
    ) -> None:
        openpyxl = pytest.importorskip("openpyxl")
        path = tmp_path / "out.xlsx"
        self._write(script, path)
        sheet = openpyxl.load_workbook(path)["student_demographics"]
        for row in sheet.iter_rows(values_only=True):
            assert "@" not in " ".join(str(v) for v in row if v is not None)


class TestReadWorkbookRows:
    def test_round_trip_matches_what_was_written(
        self, script: ModuleType, tmp_path: Path
    ) -> None:
        pytest.importorskip("openpyxl")
        path = tmp_path / "out.xlsx"
        writer = TestWriteWorkbook()
        writer._write(script, path)
        assert script.read_workbook_rows(path) == writer._rows(script)

    def test_blank_cells_come_back_as_empty_strings(
        self, script: ModuleType, tmp_path: Path
    ) -> None:
        """openpyxl reads an empty cell as None; validate_rows needs ''."""
        pytest.importorskip("openpyxl")
        path = tmp_path / "out.xlsx"
        TestWriteWorkbook()._write(script, path)
        unmatched = [
            row
            for row in script.read_workbook_rows(path)
            if row["demographics_source"] == "not matched"
        ]
        assert unmatched
        assert all(row["gender"] == "" for row in unmatched)

    def test_written_file_passes_validation(
        self, script: ModuleType, tmp_path: Path
    ) -> None:
        pytest.importorskip("openpyxl")
        path = tmp_path / "out.xlsx"
        TestWriteWorkbook()._write(script, path)
        script.validate_rows(script.read_workbook_rows(path), _roster(script))

    def test_unexpected_header_raises(
        self, script: ModuleType, tmp_path: Path
    ) -> None:
        openpyxl = pytest.importorskip("openpyxl")
        path = tmp_path / "out.xlsx"
        workbook = openpyxl.Workbook()
        workbook.worksheets[0].title = "student_demographics"
        workbook.worksheets[0].append(["nope"])
        workbook.save(path)
        with pytest.raises(ValueError, match="header"):
            script.read_workbook_rows(path)
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-quill-seta-demographics
uv run --with openpyxl pytest tests/test_extract_quill_seta_ed_demographics.py -k WriteWorkbook -v
```

Expected: FAIL with
`AttributeError: module ... has no attribute 'write_workbook'`.

- [ ] **Step 3: Implement the writer**

Add after `write_key_file`:

```python
DATA_DICTIONARY: tuple[tuple[str, str, str, str], ...] = (
    (
        "quill_student_id",
        "Quill platform user ID for the student, unchanged from the roster export.",
        "Quill roster export, column 'Studetn ID'",
        "Integer. Join key to Quill platform data. Not a school district identifier.",
    ),
    (
        "classroom_code",
        "Pseudonymous code for the Quill classroom section.",
        "Assigned by this script",
        "C01 through C09. Mapping to section names is retained by the data supplier.",
    ),
    (
        "teacher_code",
        "Pseudonymous code for the teacher of record for the section.",
        "Assigned by this script",
        "T1, T2. Maps 1:1 to school. Mapping to names is retained by the data supplier.",
    ),
    (
        "race_ethnicity",
        "Race and ethnicity as recorded in the student information system.",
        "int_extracts__student_enrollments.race_ethnicity",
        "Asian, BL-AA, Hispanic or Latino, AI-AN, NH-OPI, 2+ races, White, DTS. "
        "DTS means declined to state. Blank when the student was not matched.",
    ),
    (
        "gender",
        "Gender as recorded in the student information system.",
        "int_extracts__student_enrollments.gender",
        "Female, Male, Non-Binary. Blank when the student was not matched.",
    ),
    (
        "meal_status",
        "National School Lunch Program eligibility for the school year.",
        "int_extracts__student_enrollments.lunch_status",
        "Free, Reduced, Paid. Direct certification is reported as Free. "
        "Blank when the student was not matched.",
    ),
    (
        "iep_status",
        "Whether the student had an active individualized education program.",
        "int_extracts__student_enrollments.iep_status",
        "Has IEP, No IEP. Blank when the student was not matched.",
    ),
    (
        "mll_status",
        "Multilingual learner status.",
        "int_extracts__student_enrollments.ml_status",
        "ML, Not ML. Blank when the student was not matched.",
    ),
    (
        "demographics_source",
        "Which school year's enrollment record supplied this row's values.",
        "Assigned by this script",
        "SY25-26 for the pilot year. 'SYxx-yy (fallback)' when the student was "
        "not enrolled in the pilot year and an earlier year was used. "
        "'not matched' when no enrollment record was found at all.",
    ),
)

_DICTIONARY_HEADERS = ("column", "definition", "source", "coding")


def write_workbook(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    """Write the two-sheet deliverable."""
    # trunk-ignore(pyright/reportMissingModuleSource): openpyxl is a PEP 723 script dep
    import openpyxl

    workbook = openpyxl.Workbook()

    # worksheets[0] rather than .active: pyright types .active as Optional and
    # trunk runs pyright over scripts/.
    data_sheet = workbook.worksheets[0]
    data_sheet.title = "student_demographics"
    data_sheet.append(list(OUTPUT_COLUMNS))
    for row in rows:
        data_sheet.append([row[column] for column in OUTPUT_COLUMNS])

    dictionary_sheet = workbook.create_sheet("data_dictionary")
    dictionary_sheet.append(list(_DICTIONARY_HEADERS))
    for entry in DATA_DICTIONARY:
        dictionary_sheet.append(list(entry))

    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)


def read_workbook_rows(path: Path) -> list[dict[str, object]]:
    """Read the delivered sheet back, so validation runs against the real file.

    An in-memory check cannot catch a serialization mistake, and the file is
    what gets sent. openpyxl reads a blank cell as None; coerce to '' so the
    whitelist in validate_rows sees the same vocabulary it wrote.
    """
    # trunk-ignore(pyright/reportMissingModuleSource): openpyxl is a PEP 723 script dep
    import openpyxl

    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheet = workbook["student_demographics"]
    rows = sheet.iter_rows(values_only=True)

    header = tuple(next(rows))
    if header != OUTPUT_COLUMNS:
        raise ValueError(f"unexpected workbook header {header!r}")

    parsed: list[dict[str, object]] = [
        {
            column: "" if value is None else value
            for column, value in zip(OUTPUT_COLUMNS, row, strict=True)
        }
        for row in rows
    ]

    workbook.close()

    return parsed
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-quill-seta-demographics
uv run --with openpyxl pytest tests/test_extract_quill_seta_ed_demographics.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-quill-seta-demographics
git add scripts/extract_quill_seta_ed_demographics.py tests/test_extract_quill_seta_ed_demographics.py
git commit -m "feat(scripts): two-sheet workbook writer with data dictionary

Refs #4848"
```

---

### Task 4: BigQuery fetch, CLI, and the real run

**Files:**

- Modify: `scripts/extract_quill_seta_ed_demographics.py`

**Interfaces:**

- Consumes: everything from Tasks 1 through 3.
- Produces:
  - `SOURCE_TABLE: str`
  - `build_query(table: str) -> str`
  - `fetch_demographics(client, emails, pilot_year, table) -> dict[str, Demographics]`
  - `main(argv: Sequence[str] | None = None) -> int`

No unit test: this task's verification is a real run against the real roster,
because the only thing worth checking is whether the query and the assembly hold
up against production data.

- [ ] **Step 1: Implement the query and CLI**

Add to the imports at the top of the script:

```python
import argparse
import datetime
import sys
from collections import Counter
```

Add after `write_workbook`:

```python
SOURCE_TABLE = "teamster-332318.kipptaf_extracts.int_extracts__student_enrollments"


def build_query(table: str) -> str:
    """One row per roster email: the pilot year if present, else the most recent.

    rn_year = 1 picks the student's primary enrollment stint within a year, so
    a mid-year school move does not produce two rows for one student-year.
    """
    return f"""
        with
            ranked as (
                select
                    lower(student_email) as student_email,
                    student_number,
                    academic_year,
                    race_ethnicity,
                    gender,
                    lunch_status,
                    iep_status,
                    ml_status,
                    row_number() over (
                        partition by lower(student_email)
                        order by academic_year desc
                    ) as year_rank,
                from `{table}`
                where
                    lower(student_email) in unnest(@emails)
                    and academic_year <= @pilot_year
                    and rn_year = 1
            )
        select * except (year_rank)
        from ranked
        where year_rank = 1
    """


def fetch_demographics(
    client,
    emails: Sequence[str],
    pilot_year: int,
    table: str = SOURCE_TABLE,
) -> dict[str, Demographics]:
    """Query the warehouse for one demographics record per roster email."""
    from google.cloud import bigquery

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ArrayQueryParameter("emails", "STRING", list(emails)),
            bigquery.ScalarQueryParameter("pilot_year", "INT64", pilot_year),
        ]
    )

    results: dict[str, Demographics] = {}
    for row in client.query(build_query(table), job_config=job_config).result():
        results[row["student_email"]] = Demographics(
            academic_year=row["academic_year"],
            student_number=row["student_number"],
            race_ethnicity=row["race_ethnicity"],
            gender=row["gender"],
            meal_status=row["lunch_status"],
            iep_status=row["iep_status"],
            mll_status=row["ml_status"],
        )

    return results


def _report_cell_counts(rows: Sequence[Mapping[str, object]]) -> None:
    """Print the counts that decide whether this file is safe to send."""
    for column in (
        "race_ethnicity",
        "gender",
        "meal_status",
        "iep_status",
        "mll_status",
        "demographics_source",
    ):
        counts = Counter(str(row[column]) for row in rows)
        print(f"\n{column}:")
        for value, count in sorted(counts.items(), key=lambda item: -item[1]):
            flag = "  <-- singleton" if count == 1 else ""
            print(f"  {value or '(blank)':<24} {count:>4}{flag}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roster", type=Path, required=True, help="roster .xlsx path")
    parser.add_argument(
        "--output-dir", type=Path, required=True, help="directory for the workbook"
    )
    parser.add_argument(
        "--key-file",
        type=Path,
        required=True,
        help="retained re-identification key (JSON); never commit or transmit",
    )
    parser.add_argument("--pilot-year", type=int, default=2025)
    parser.add_argument("--gcp-project", default="teamster-332318")
    args = parser.parse_args(argv)

    from google.cloud import bigquery

    roster = read_roster(args.roster)
    print(f"roster: {len(roster)} rows, {len({e.quill_student_id for e in roster})} students")

    prior_classrooms, prior_teachers = read_codebook(args.key_file)
    classroom_codes = assign_codes(
        (entry.classroom_name for entry in roster), prior_classrooms, "C", 2
    )
    teacher_codes = assign_codes(
        (entry.teacher_name for entry in roster), prior_teachers, "T", 1
    )

    emails = sorted({entry.student_email for entry in roster})
    demographics = fetch_demographics(
        bigquery.Client(project=args.gcp_project), emails, args.pilot_year
    )
    print(f"matched {len(demographics)} of {len(emails)} emails")

    rows = build_output_rows(
        roster, demographics, args.pilot_year, classroom_codes, teacher_codes
    )
    validate_rows(rows, roster)

    extract_date = datetime.date.today().isoformat()
    workbook_path = (
        args.output_dir / f"quill_seta_ed_student_demographics_{extract_date}.xlsx"
    )
    write_workbook(workbook_path, rows)

    # Re-validate from disk. The check above proves the rows were built right;
    # this one proves the file that gets sent is the file we built.
    validate_rows(read_workbook_rows(workbook_path), roster)

    write_key_file(
        args.key_file,
        classroom_codes,
        teacher_codes,
        build_key_records(roster, demographics, classroom_codes, teacher_codes),
    )

    _report_cell_counts(rows)
    print(f"\nworkbook: {workbook_path}")
    print(f"key file (do not send): {args.key_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Re-run the unit tests**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-quill-seta-demographics
uv run --with openpyxl pytest tests/test_extract_quill_seta_ed_demographics.py -v
```

Expected: PASS. The new imports must not break module load.

- [ ] **Step 3: Run against the real roster**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-quill-seta-demographics
uv run scripts/extract_quill_seta_ed_demographics.py \
  --roster "/workspaces/teamster/.claude/scratch/Quill request/Quill_KIPP_for SETA-ED (2).xlsx" \
  --output-dir "/workspaces/teamster/.claude/scratch/Quill request/output" \
  --key-file "/workspaces/teamster/.claude/scratch/Quill request/reidentification-key.json"
```

Expected, exactly:

- `roster: 269 rows, 248 students`
- `matched 245 of 248 emails`
- no traceback from `validate_rows`
- `demographics_source` counts totalling 269, with `SY24-25 (fallback)` present
  and `not matched` at 3 roster rows
- `race_ethnicity` showing two singleton cells (`AI-AN`, `NH-OPI`)

If `matched` is not 245, stop and report — the warehouse changed since the
design probe, and the discrepancy needs explaining before anything is sent.

- [ ] **Step 4: Confirm the deliverable holds no identifiers**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-quill-seta-demographics
uv run --with openpyxl python -c "
import openpyxl, pathlib, sys
d = pathlib.Path('/workspaces/teamster/.claude/scratch/Quill request/output')
book = openpyxl.load_workbook(sorted(d.glob('*.xlsx'))[-1])
sheet = book['student_demographics']
cells = [str(v) for row in sheet.iter_rows(values_only=True) for v in row if v is not None]
print('rows', sheet.max_row - 1, 'sheets', book.sheetnames)
print('at signs', sum('@' in c for c in cells))
print('sample', cells[:12])
"
```

Expected: `rows 269`, `sheets ['student_demographics', 'data_dictionary']`,
`at signs 0`.

- [ ] **Step 5: Confirm the key file stayed out of git**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-quill-seta-demographics
git status --porcelain
```

Expected: only `scripts/extract_quill_seta_ed_demographics.py` modified. The
workbook, the key file, and the roster all live under
`/workspaces/teamster/.claude/scratch/`, which is gitignored and outside the
worktree. If anything under `.claude/scratch/` appears here, stop — a path
argument was pointed at the wrong place.

- [ ] **Step 6: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-quill-seta-demographics
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  scripts/extract_quill_seta_ed_demographics.py \
  tests/test_extract_quill_seta_ed_demographics.py </dev/null
git add scripts/extract_quill_seta_ed_demographics.py
git commit -m "feat(scripts): warehouse query and CLI for the demographics extract

Refs #4848"
```

Fix any ruff or bandit finding before committing. A `subprocess` or SQL-string
finding here means the query was built by interpolation rather than by query
parameters — fix the code, do not suppress the rule.

---

### Task 5: Documentation

**Files:**

- Create: `docs/reference/quill-seta-ed-demographics-extract.md`
- Modify: `mkdocs.yml` (nav, `Reference` section)
- Modify: `scripts/CLAUDE.md` (script catalog table)

- [ ] **Step 1: Write the reference page**

Create `docs/reference/quill-seta-ed-demographics-extract.md`. It must contain,
in this order:

1. A one-paragraph purpose statement naming the agreement and the pilot year.
1. **Identifiers** — that the roster's `Studetn ID` is a Quill platform ID and
   not a KIPP `student_number`, that the join runs on student email, and that
   the delivered workbook carries no KIPP identifier.
1. **Data dictionary** — a markdown table with the same nine rows as the
   `DATA_DICTIONARY` constant, columns `column | definition | source | coding`.
   Keep them in sync; the workbook sheet is generated from the constant.
1. **Lineage** — `int_extracts__student_enrollments` filtered to
   `academic_year = 2025` and `rn_year = 1`, joined on `lower(student_email)`,
   with the label maps traced to `rpt_gsheets__csgf_enrollment`.
1. **Inclusion and exclusion rules** — one row per student-classroom pair;
   students unmatched in the pilot year fall back to their most recent prior
   year; students never matched ship blank with `demographics_source` set to
   `not matched`; grade level and school are excluded because every student is
   grade 8 and teacher code separates the schools 1:1.
1. **Rerun steps** — the exact command from Task 4 Step 3, with the roster path
   shown as a placeholder such as `{path to roster .xlsx}` rather than a real
   path.
1. **Handling of the retained key** — written to `.claude/scratch/`, never
   committed, never transmitted, reused on rerun so codes stay stable.

The page must name no student, no staff member, and must not state which code
corresponds to which classroom, teacher, or school. Fenced code blocks need a
language (`bash`, `sql`, or `text`).

- [ ] **Step 2: Add the nav entry**

In `mkdocs.yml`, under `nav:` → `Reference:`, after the `Automation Conditions`
line, add:

```yaml
- Quill Pilot Demographics Extract:
    reference/quill-seta-ed-demographics-extract.md
```

- [ ] **Step 3: Add the script catalog row**

In `scripts/CLAUDE.md`, in the Script Catalog table, add a row:

```markdown
| `extract_quill_seta_ed_demographics.py` | One-shot: de-identified demographics
workbook for the Quill pilot research partner. Roster path, output dir, and
key-file path are arguments — roster data never enters git. Needs PEP 723 deps,
so plain `uv run scripts/...` works. See #4848. |
```

- [ ] **Step 4: Verify the docs build and lint**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-quill-seta-demographics
uv run --group docs mkdocs build --strict
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  docs/reference/quill-seta-ed-demographics-extract.md \
  scripts/CLAUDE.md mkdocs.yml </dev/null
```

Expected: build succeeds with no warnings about the new page, and Trunk reports
no markdownlint issues. `mkdocs build` does not run markdownlint, so both
commands are required.

- [ ] **Step 5: Commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-quill-seta-demographics
git add docs/reference/quill-seta-ed-demographics-extract.md mkdocs.yml scripts/CLAUDE.md
git commit -m "docs: reference page for the Quill pilot demographics extract

Refs #4848"
```

---

## Done When

- `uv run --with openpyxl pytest tests/test_extract_quill_seta_ed_demographics.py`
  passes.
- The real run reports 269 roster rows, 248 students, 245 matched emails, and
  `validate_rows` raises nothing.
- The written workbook has 269 data rows, two sheets, and zero `@` characters.
- `git status --porcelain` shows no roster, workbook, or key file staged.
- Trunk reports no issues on the script, the test, the docs page, `mkdocs.yml`,
  and `scripts/CLAUDE.md`.
- `mkdocs build --strict` succeeds.

## Deliberately Not In This Plan

- Sending the workbook. That stays with the requester.
- Collapsing rare race categories. The default ships real categories; the cell
  counts printed in Task 4 Step 3 are what the requester uses to decide
  otherwise.
- Confirming the five fields against Exhibit A of the agreement. That is a
  question for the agreement owner, not a code change.

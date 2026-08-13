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
    def test_known_codes(self, script: ModuleType, code: str, expected: str) -> None:
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
    def test_known_codes(self, script: ModuleType, code: str, expected: str) -> None:
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
    def test_known_codes(self, script: ModuleType, code: str, expected: str) -> None:
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

    def test_unmatched_student_is_blank_and_flagged(self, script: ModuleType) -> None:
        rows = script.build_output_rows(_roster(script), {}, 2025, {}, {})
        assert rows[2]["demographics_source"] == "not matched"
        assert rows[2]["race_ethnicity"] == ""
        assert rows[2]["gender"] == ""
        assert rows[2]["meal_status"] == ""
        assert rows[2]["iep_status"] == ""
        assert rows[2]["mll_status"] == ""

    def test_duplicate_student_gets_both_classrooms(self, script: ModuleType) -> None:
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

    def test_columns_are_exactly_output_columns(self, script: ModuleType) -> None:
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

    def test_unmatched_student_has_no_student_number(self, script: ModuleType) -> None:
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

    def test_distinct_id_count_mismatch_raises(self, script: ModuleType) -> None:
        """Row count can match while distinct quill_student_id count does not."""
        rows = self._valid(script)
        rows[1]["quill_student_id"] = rows[0]["quill_student_id"]
        with pytest.raises(ValueError, match="distinct quill_student_id"):
            script.validate_rows(rows, _roster(script))

    def test_matched_student_with_blank_demographic_raises(
        self, script: ModuleType
    ) -> None:
        """A NULL source field must not ship as an unmatched-looking blank."""
        rows = script.build_output_rows(
            _roster(script),
            {
                "aaa@example.org": script.Demographics(
                    2025, 900001, "B", "F", "", "No IEP", "Not ML"
                )
            },
            2025,
            {"Room Alpha": "C01", "Room Beta": "C02"},
            {"Teacher One": "T1", "Teacher Two": "T2"},
        )
        with pytest.raises(ValueError, match="meal_status"):
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
                [
                    1001,
                    "Ann Ant",
                    "AAA@Example.org",
                    "Room Alpha",
                    "Teacher One",
                    "t1@example.org",
                ],
                [
                    1002,
                    "Bob Bee",
                    "bbb@example.org",
                    "Room Beta",
                    "Teacher Two",
                    "t2@example.org",
                ],
            ],
        )
        roster = script.read_roster(path)
        assert len(roster) == 2
        assert roster[0].quill_student_id == 1001
        assert roster[0].classroom_name == "Room Alpha"
        assert roster[0].teacher_name == "Teacher One"

    def test_email_is_lowercased_and_stripped(
        self, script: ModuleType, tmp_path: Path
    ) -> None:
        """Both halves of .strip().lower() are load-bearing for the join."""
        path = tmp_path / "roster.xlsx"
        self._workbook(
            path,
            [
                [
                    1001,
                    "Ann Ant",
                    "  AAA@Example.org  ",
                    "Room Alpha",
                    "Teacher One",
                    "t1@example.org",
                ]
            ],
        )
        assert script.read_roster(path)[0].student_email == "aaa@example.org"

    def test_bool_id_raises(self, script: ModuleType, tmp_path: Path) -> None:
        """bool is an int subclass; True must not become id 1."""
        path = tmp_path / "roster.xlsx"
        self._workbook(
            path,
            [
                [
                    True,
                    "Ann Ant",
                    "aaa@example.org",
                    "Room Alpha",
                    "Teacher One",
                    "t1@example.org",
                ]
            ],
        )
        with pytest.raises(ValueError, match="unexpected roster id cell"):
            script.read_roster(path)

    def test_fractional_id_raises(self, script: ModuleType, tmp_path: Path) -> None:
        path = tmp_path / "roster.xlsx"
        self._workbook(
            path,
            [
                [
                    1001.7,
                    "Ann Ant",
                    "aaa@example.org",
                    "Room Alpha",
                    "Teacher One",
                    "t1@example.org",
                ]
            ],
        )
        with pytest.raises(ValueError, match="fractional roster id cell"):
            script.read_roster(path)

    def test_blank_email_raises(self, script: ModuleType, tmp_path: Path) -> None:
        """str(None) would become the literal 'none' and never match."""
        path = tmp_path / "roster.xlsx"
        self._workbook(
            path,
            [[1001, "Ann Ant", None, "Room Alpha", "Teacher One", "t1@example.org"]],
        )
        with pytest.raises(ValueError, match="blank required cell"):
            script.read_roster(path)

    def test_blank_trailing_rows_are_skipped(
        self, script: ModuleType, tmp_path: Path
    ) -> None:
        path = tmp_path / "roster.xlsx"
        self._workbook(
            path,
            [
                [
                    1001,
                    "Ann Ant",
                    "aaa@example.org",
                    "Room Alpha",
                    "Teacher One",
                    "t1@example.org",
                ],
                [None, None, None, None, None, None],
            ],
        )
        assert len(script.read_roster(path)) == 1

    def test_unexpected_headers_raise(self, script: ModuleType, tmp_path: Path) -> None:
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
            path,
            {},
            {},
            [{"quill_student_id": 1001, "student_email": "aaa@example.org"}],
        )
        stored = json.loads(path.read_text())
        assert stored["students"][0]["student_email"] == "aaa@example.org"


class TestWriteKeyFileMerge:
    """A rerun must not destroy prior students dropped from the current roster."""

    def test_prior_only_student_is_preserved(
        self, script: ModuleType, tmp_path: Path
    ) -> None:
        import json

        path = tmp_path / "key.json"
        script.write_key_file(
            path,
            {},
            {},
            [
                {"quill_student_id": 1001, "student_email": "aaa@example.org"},
                {"quill_student_id": 2002, "student_email": "left@example.org"},
            ],
        )
        # Second run's roster no longer includes 2002 (the student left the
        # pilot between the pre- and post-period deliveries).
        script.write_key_file(
            path,
            {},
            {},
            [{"quill_student_id": 1001, "student_email": "aaa@example.org"}],
        )
        stored = json.loads(path.read_text())
        ids = {record["quill_student_id"] for record in stored["students"]}
        assert ids == {1001, 2002}

    def test_current_run_wins_on_conflict(
        self, script: ModuleType, tmp_path: Path
    ) -> None:
        import json

        path = tmp_path / "key.json"
        script.write_key_file(
            path, {}, {}, [{"quill_student_id": 1001, "classroom_code": "C01"}]
        )
        script.write_key_file(
            path, {}, {}, [{"quill_student_id": 1001, "classroom_code": "C02"}]
        )
        stored = json.loads(path.read_text())
        record = next(r for r in stored["students"] if r["quill_student_id"] == 1001)
        assert record["classroom_code"] == "C02"

    def test_backup_snapshot_is_written_on_rerun(
        self, script: ModuleType, tmp_path: Path
    ) -> None:
        path = tmp_path / "key.json"
        script.write_key_file(path, {}, {}, [{"quill_student_id": 1001}])
        script.write_key_file(path, {}, {}, [{"quill_student_id": 1001}])
        assert path.with_name("key.json.bak").exists()

    def test_no_bak_on_first_write(self, script: ModuleType, tmp_path: Path) -> None:
        path = tmp_path / "key.json"
        script.write_key_file(path, {}, {}, [{"quill_student_id": 1001}])
        assert not path.with_name("key.json.bak").exists()


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

    def test_unexpected_header_raises(self, script: ModuleType, tmp_path: Path) -> None:
        openpyxl = pytest.importorskip("openpyxl")
        path = tmp_path / "out.xlsx"
        workbook = openpyxl.Workbook()
        workbook.worksheets[0].title = "student_demographics"
        workbook.worksheets[0].append(["nope"])
        workbook.save(path)
        with pytest.raises(ValueError, match="header"):
            script.read_workbook_rows(path)

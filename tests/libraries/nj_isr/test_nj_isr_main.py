from datetime import date
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from google.cloud import bigquery

from teamster.libraries.nj_isr import __main__ as cli
from teamster.libraries.nj_isr.layout import OutputFile
from teamster.libraries.nj_isr.publish import PublishResult

SID = "1000000001"
TAG = "2026_Spring_NJSLA"
ALL_DISTRICTS = (
    "2026_Spring_7325-965_ISR_SLA_Combined.pdf",
    "2026_Spring_1799-111_ISR_SLA_Combined.pdf",
    "2026_Spring_7899-925_ISR_SLA_Combined.pdf",
)

ENROLLMENT = {
    "student_number": 101,
    "academic_year": 2026,
    "rn_year": 1,
    "enroll_status": 0,
    "region": "Newark",
    "schoolid": 133570965,
    "school_name": "KIPP TEAM Academy",
    "last_name": "Rivera",
    "first_name": "Alex",
    "dob": date(2015, 3, 4),
}


def fake_pages(path: Path) -> list[str]:
    district = path.name.split("_")[2].split("-")[0]
    footer = f"{district}.{district}_965.1"
    text = "\r\n".join(
        [
            "English Language Arts",
            "ALEX B. RIVERA ENROLLED GRADE: 5",
            f"Student ID: {SID} Date of Birth: 03/04/15 Date of Testing: SPRING 2026",
        ]
    )
    return [text + footer, text + footer]


class FakeJob:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def result(self) -> list[dict[str, Any]]:
        return self._rows


class FakeClient:
    """Answers the 3 warehouse queries with 1 invented student."""

    queries: list[tuple[str, bigquery.QueryJobConfig | None]] = []

    def __init__(self, project: str | None = None) -> None:
        pass

    def query(
        self, sql: str, job_config: bigquery.QueryJobConfig | None = None
    ) -> FakeJob:
        FakeClient.queries.append((sql, job_config))

        if "int_cambium__all_assessments" in sql:
            return FakeJob([{"state_id": SID, "student_number": 101}])

        if "state_studentnumber is not null" in sql:
            return FakeJob([{"student_number": 101, "state_id": SID}])

        return FakeJob([ENROLLMENT])


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[Any]]:
    """Replaces every outside call main makes, and records the Drive ones."""
    recorded: dict[str, list[Any]] = {
        "load_credentials": [],
        "GoogleDriveApi": [],
        "publish": [],
    }
    FakeClient.queries = []

    def load_credentials() -> object:
        recorded["load_credentials"].append(())
        return object()

    def drive_api(credentials: object) -> object:
        recorded["GoogleDriveApi"].append(credentials)
        return object()

    def publish(*args: Any, **kwargs: Any) -> PublishResult:
        recorded["publish"].append(kwargs)
        return PublishResult(
            links={},
            sheets={},
            trashed=[],
            readers={},
            root_name="Test root",
            root_readers=[],
            orphans_kept=[],
        )

    def write_output_pdf(file: OutputFile, out_dir: Path) -> Path:
        return out_dir / file.file_name

    monkeypatch.setattr(cli.bigquery, "Client", FakeClient)
    monkeypatch.setattr(cli, "read_page_texts", fake_pages)
    monkeypatch.setattr(cli, "write_output_pdf", write_output_pdf)
    monkeypatch.setattr(cli, "load_credentials", load_credentials)
    monkeypatch.setattr(cli, "GoogleDriveApi", drive_api)
    monkeypatch.setattr(cli, "publish", publish)
    return recorded


def input_folder(tmp_path: Path, names: tuple[str, ...] = ALL_DISTRICTS) -> Path:
    folder = tmp_path / "Spring 2026 ISRs"
    folder.mkdir()
    for name in names:
        (folder / name).write_bytes(b"")
    return folder


def test_dry_run_never_touches_drive_credentials(tmp_path, calls):
    assert cli.main(["--input", str(input_folder(tmp_path)), "--dry-run"]) == 0

    assert calls["load_credentials"] == []
    assert calls["GoogleDriveApi"] == []
    assert calls["publish"] == []


def test_dry_run_writes_the_checks_csv_inside_the_input_folder(tmp_path, calls):
    folder = input_folder(tmp_path)

    cli.main(["--input", str(folder), "--dry-run"])

    assert (folder / f"nj_isr_checks_{TAG}.csv").is_file()
    assert not (tmp_path / f"nj_isr_checks_{TAG}.csv").exists()


def test_missing_district_stops_before_loading_credentials(tmp_path, calls, capsys):
    folder = input_folder(tmp_path, ALL_DISTRICTS[:1])

    assert cli.main(["--input", str(folder), "--root-folder", "root1"]) == 1

    assert calls["load_credentials"] == []
    assert calls["publish"] == []
    assert "Stopping, nothing was published" in capsys.readouterr().err


def test_real_run_passes_eastern_time_and_the_trash_flag(tmp_path, calls):
    folder = input_folder(tmp_path)

    assert cli.main(["--input", str(folder), "--root-folder", "root1"]) == 0

    assert len(calls["load_credentials"]) == 1
    (kwargs,) = calls["publish"]
    assert kwargs["ran_at"].tzinfo == ZoneInfo("America/New_York")
    assert kwargs["allow_trash"] is False
    assert kwargs["create_missing"] is False


def test_student_queries_are_limited_to_regions_with_report_folders(tmp_path, calls):
    cli.main(["--input", str(input_folder(tmp_path)), "--dry-run"])

    student_queries = [
        (sql, job_config)
        for sql, job_config in FakeClient.queries
        if "int_students__student_enrollments" in sql
    ]
    assert len(student_queries) == 2
    for sql, job_config in student_queries:
        assert "region in unnest(@regions)" in sql
        assert job_config is not None
        regions = next(p for p in job_config.query_parameters if p.name == "regions")
        assert isinstance(regions, bigquery.ArrayQueryParameter)
        assert regions.values == ["Camden", "Newark", "Paterson"]

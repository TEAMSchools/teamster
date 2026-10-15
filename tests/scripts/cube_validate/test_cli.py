"""analyze end to end on a synthetic snapshot. No live calls."""

import datetime as dt
import json

import pytest
import yaml

pytest.importorskip("tableauhyperapi")

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest registers cube_validate at runtime
from cube_validate import cells, cli, hyper, snapshot  # noqa: E402

CHECKS = {
    "dashboard": "d",
    "workbook": "W",
    "workbook_luid": "l",
    "review_project_luid": "ddc817c2-6bc7-4bca-8be9-e385f95b9ebc",
    "dashboards": ["Overview"],
    "datasource": "ds",
    "dashboard_table": "p.d.t",
    "period_start": "2026-10-05",
    "window": {
        "start": "15:30",
        "end": "06:00",
        "extract_after": "15:00",
        "tz": "America/New_York",
    },
    "cost_cap_gb": 50,
    "cube": {
        "view": "v",
        "date": "attendance_date",
        "members": [
            "lea_student_identifier",
            "attendance_date",
            "locations_abbreviation",
        ],
    },
    "rows": {
        "student_key": "student",
        "date_key": "day",
        "scope_key": "school",
        "key": {
            "student": {
                "tableau": "student_number",
                "cube": 'cast("{p}lea_student_identifier" as bigint)',
            },
            "day": {"tableau": "calendardate", "cube": "attendance_date"},
            "school": {
                "tableau": "school_abbreviation",
                "cube": "locations_abbreviation",
            },
        },
    },
    "sheets": {
        "ADA": {
            "students": "Students",
            "dims": {
                "School": {
                    "tableau": "school_abbreviation",
                    "cube": "locations_abbreviation",
                    "cube_column": "locations_abbreviation",
                }
            },
            "measures": {"ADA": {"cube": "avg_daily_attendance"}},
        }
    },
    "cuts": [{"id": "default"}],
}


def test_analyze_writes_report_and_hand_checks(tmp_path):
    checks_path = tmp_path / "c.yml"
    checks_path.write_text(yaml.safe_dump(CHECKS))
    snap = snapshot.new_snapshot("d", dt.datetime(2026, 10, 15, 16, 0), root=tmp_path)
    d = dt.date(2026, 10, 6)
    hyper.write_table(
        snap.extract,
        "Extract",
        "Extract",
        [
            ("student_number", "bigint"),
            ("calendardate", "date"),
            ("school_abbreviation", "text"),
        ],
        [(1, d, "Rise"), (2, d, "Rise")],
    )
    hyper.write_table(
        snap.cube,
        "cube",
        "rows",
        [
            ("lea_student_identifier", "double"),
            ("attendance_date", "date"),
            ("locations_abbreviation", "text"),
        ],
        [(1.0, d, "Rise"), (2.0, d, "Rise")],
    )
    snap.export_path("default", "ADA").write_bytes(
        b"School,ADA,Students\nRise,94.2%,2\n"
    )
    snap.answers.write_text(
        json.dumps(
            {
                cells.answer_key("default", "ADA"): {
                    "query": {},
                    "sql": "SELECT",
                    "last_refresh": "x",
                    "data": [
                        {
                            "v.locations_abbreviation": "Rise",
                            "v.avg_daily_attendance": "0.942",
                        }
                    ],
                }
            }
        )
    )
    snapshot.write_manifest(
        snap,
        {
            "scope": ["Rise"],
            "invariants": {"capture completeness": True},
            "review_copy": {"name": "ZZ-REVIEW x"},
            "cuts": {"default": {}},
        },
    )
    report, trust = cli.analyze_snapshot(cli.config.load_checks(checks_path), snap)
    text = report.read_text()
    assert "| pass | <10 |" in text and trust.startswith("Pending")
    assert (snap.analysis / "hand_checks.md").exists()

from datetime import date
from pathlib import Path

import pytest

from teamster.goal_setting.adapters import archive, goals_sheet, iready_boy, roster_sql
from teamster.goal_setting.config import load_rules

from .fixtures.roster_small import student, untested

REPO = Path(__file__).resolve().parents[2]
GROUP = load_rules(REPO / "config/goal_setting/ay2026.yaml").group("nj_math_1_2")


def test_archive_round_trip_is_lossless(tmp_path):
    recs = [student(projected_score=405.0), untested()]
    meta = archive.write_input(archive.records_to_rows(recs), tmp_path / "in.csv")
    back = archive.rows_to_records(
        archive.read_input(tmp_path / "in.csv", meta["sha256"])
    )
    assert back == recs
    assert meta["row_count"] == 2 and len(meta["sha256"]) == 64
    assert meta["counts_by_school_grade"] == [
        {"region": "Newark", "school": "TEAM", "grade_level": 1, "n": 2}
    ]
    assert meta["tested_share_by_school_grade"] == [
        {"region": "Newark", "school": "TEAM", "grade_level": 1, "share": 0.5}
    ]


def test_archive_hash_mismatch_aborts(tmp_path):
    archive.write_input(archive.records_to_rows([student()]), tmp_path / "in.csv")
    with pytest.raises(archive.ArchiveMismatch):
        archive.read_input(tmp_path / "in.csv", "0" * 64)


def test_iready_sql_names_group_filters():
    q = iready_boy.sql(GROUP, 2026)
    assert "academic_year = 2026" in q
    assert "grade_level in (1, 2)" in q
    assert "region in ('Newark', 'Camden', 'Paterson')" in q
    assert "iready_subject = 'Math'" in q
    assert "test_round = 'BOY'" in q
    assert "annual_typical_growth_measure" in q and "annual_stretch_growth_measure" in q
    assert "stg_google_sheets__iready__crosswalk" in q
    assert "TODO(#5317)" in q


def test_goals_sql_maps_subject_to_illuminate_area():
    q = goals_sheet.sql(GROUP, 2026)
    assert (
        "'Mathematics'" in q and "grade_band_goal" in q and "academic_year = 2026" in q
    )


def test_inline_targets_from_config():
    g = GROUP.model_copy(
        update={
            "target": GROUP.target.model_copy(
                update={
                    "from_": "inline",
                    "column": None,
                    "values": {"Newark": {1: 0.35, 2: 0.24}},
                }
            )
        }
    )
    assert goals_sheet.inline_targets(g) == {("Newark", 1): 0.35, ("Newark", 2): 0.24}


def test_targets_from_rows_reports_every_missing_pair():
    rows = [{"region": "Newark", "grade_level": 1, "target": 0.35}]
    with pytest.raises(goals_sheet.MissingTargets) as e:
        goals_sheet.targets_from_rows(rows, GROUP)
    msg = str(e.value)
    assert (
        "Camden grade 1" in msg
        and "Paterson grade 2" in msg
        and "Newark grade 1" not in msg
    )


def test_baseline_sql_pins_a_date():
    q = roster_sql.baseline_sql(GROUP, 2026, date(2026, 9, 1))
    assert "'2026-09-01'" in q and "grade_level in (1, 2)" in q

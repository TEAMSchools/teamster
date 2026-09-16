from datetime import date
from pathlib import Path

import pytest

from teamster.goal_setting.config import (
    ConfigError,
    load_crosswalk,
    load_rules,
)

REPO = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO / "config" / "goal_setting"


def write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "rules.yaml"
    p.write_text(text)
    return p


GOOD = """
academic_year: 2026
groups:
  - name: nj_math_1_2
    regions: [Newark, Camden, Paterson]
    grades: [1, 2]
    subject: Math
    rollout_date: 2026-10-15
    source: iready_boy
    levels: {proficient: [5], approaching: [4]}
    target: {from: goals_sheet, column: grade_band_goal}
    school_goal: bubble_parameter
    bucket2: {strategy: top_approaching_to_move, ties: admit}
    bucket3: {strategy: remaining_approaching_or_stretch}
    amendments: {max_per_school_grade_subject: 3, to_buckets: [2]}
    freshness: {min_tested_share: 0.85, roster_tolerance: 0.15}
"""


def test_good_rules_file_loads(tmp_path):
    rules = load_rules(write(tmp_path, GOOD))
    g = rules.group("nj_math_1_2")
    assert rules.academic_year == 2026
    assert g.rollout_date == date(2026, 10, 15)
    assert g.levels.proficient == [5]
    assert g.bucket2.ties == "admit"


def test_unknown_strategy_lists_valid_names(tmp_path):
    bad = GOOD.replace("remaining_approaching_or_stretch", "remaining_aproaching")
    with pytest.raises(ConfigError) as e:
        load_rules(write(tmp_path, bad))
    msg = str(e.value)
    assert "remaining_aproaching" in msg
    assert "remaining_approaching_or_stretch" in msg
    assert "stretch_reachers" in msg


def test_unknown_parameter_is_rejected(tmp_path):
    bad = GOOD.replace("ties: admit", "ties: admit, tie: strict")
    with pytest.raises(ConfigError) as e:
        load_rules(write(tmp_path, bad))
    assert "tie" in str(e.value)


def test_overlapping_grades_same_region_subject_rejected(tmp_path):
    dup = GOOD + GOOD.split("groups:\n")[1].replace(
        "name: nj_math_1_2", "name: nj_math_2_only"
    ).replace("grades: [1, 2]", "grades: [2]")
    with pytest.raises(ConfigError) as e:
        load_rules(write(tmp_path, dup))
    assert "Newark" in str(e.value) and "grade 2" in str(e.value)


def test_group_missing_raises(tmp_path):
    rules = load_rules(write(tmp_path, GOOD))
    with pytest.raises(ConfigError):
        rules.group("nope")


def test_target_column_must_be_a_known_goals_column(tmp_path):
    bad = GOOD.replace("column: grade_band_goal", "column: grade_band_gaol")
    with pytest.raises(ConfigError) as e:
        load_rules(write(tmp_path, bad))
    assert "grade_band_gaol" in str(e.value)


CROSSWALK = """
programs:
  - {region: Camden, subject: Math, bucket: "Bucket 3", programid: 7374}
  - {region: Newark, subject: Reading, bucket: "Bucket 2", programid: 7374}
"""


def test_same_program_id_two_regions_loads(tmp_path):
    p = tmp_path / "x.yaml"
    p.write_text(CROSSWALK)
    xw = load_crosswalk(p)
    assert xw.program_id("Camden", "Math", "Bucket 3") == 7374
    assert xw.program_id("Newark", "Reading", "Bucket 2") == 7374


def test_same_program_id_twice_one_region_fails_naming_both(tmp_path):
    p = tmp_path / "x.yaml"
    p.write_text(
        CROSSWALK.replace("region: Newark", "region: Camden")
        .replace("subject: Reading", "subject: Math")
        .replace('bucket: "Bucket 2"', 'bucket: "Bucket 2"')
    )
    with pytest.raises(ConfigError) as e:
        load_crosswalk(p)
    assert str(e.value).count("7374") >= 2 and "Camden" in str(e.value)


def test_bucket4_has_no_program(tmp_path):
    p = tmp_path / "x.yaml"
    p.write_text(CROSSWALK)
    xw = load_crosswalk(p)
    with pytest.raises(ConfigError):
        xw.program_id("Camden", "Math", "Bucket 4")


def test_committed_config_files_validate():
    rules = load_rules(CONFIG_DIR / "ay2026.yaml")
    xw = load_crosswalk(CONFIG_DIR / "ps_programs.yaml")
    assert rules.academic_year == 2026
    assert {g.name for g in rules.groups} >= {"nj_math_1_2", "nj_math_k"}
    for region in ("Camden", "Newark", "Paterson"):
        for bucket in ("Bucket 1", "Bucket 2", "Bucket 3"):
            for subject in ("Math", "Reading"):
                assert xw.program_id(region, subject, bucket) > 0

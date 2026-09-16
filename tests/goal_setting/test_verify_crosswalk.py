from pathlib import Path

from teamster.goal_setting.config import load_crosswalk
from teamster.goal_setting.verify_crosswalk import compare, sql

REPO = Path(__file__).resolve().parents[2]
XW = load_crosswalk(REPO / "config/goal_setting/ps_programs.yaml")


def live(region, pid, name):
    return {"region": region, "programid": pid, "specprog_name": name}


def full_live():
    rows = []
    for p in XW.programs:
        disc = "ELA" if p.subject == "Reading" else "Math"
        rows.append(live(p.region, p.programid, f"{p.bucket} - {disc}"))
    return rows


def test_clean_crosswalk_has_no_problems():
    assert compare(XW, full_live()) == []


def test_missing_live_program_is_reported_with_region():
    rows = [r for r in full_live() if r["programid"] != 1638]
    (problem,) = compare(XW, rows)
    assert "Paterson" in problem and "1638" in problem and "not found" in problem


def test_live_bucket_program_absent_from_crosswalk_is_reported():
    rows = full_live() + [live("Newark", 9999, "Bucket 2 - Math")]
    (problem,) = compare(XW, rows)
    assert "9999" in problem and "not in crosswalk" in problem


def test_name_mismatch_is_reported():
    rows = full_live()
    rows[0]["specprog_name"] = "Bucket 3 - Math"  # Camden 7376 should be Bucket 1 - ELA
    problems = compare(XW, rows)
    assert any(
        "7376" in p and "Bucket 1 - ELA" in p and "Bucket 3 - Math" in p
        for p in problems
    )


def test_sql_scopes_regions_and_bucket_names():
    q = sql(["Camden", "Newark"])
    assert "like 'Bucket%'" in q and "kippcamden" in q and "kippnewark" in q


def test_sql_emits_a_valid_bigquery_regex_literal():
    q = sql(["Camden"])
    assert r"(kipp\w+)_" in q

from __future__ import annotations

import pytest

from teamster.cube_sandbox import sentinel


def test_fabricated_values_pass() -> None:
    seen = {
        "staff_directory.work_email": ["a.b@ktaf-sandbox.invalid", None],
        "staff_directory.locations_abbreviation": ["SBX001", "SBX042", None],
    }
    assert sentinel.violations(seen) == []


def test_a_real_looking_email_is_a_violation_and_is_redacted() -> None:
    # The check fails exactly when real people are being served, so it must
    # not print who they are.
    seen = {"staff_directory.work_email": ["someone@apps.teamschools.org"]}
    assert sentinel.violations(seen) == [
        "staff_directory.work_email: '***@apps.teamschools.org' is not "
        "on a .invalid domain"
    ]


def test_a_real_looking_school_is_a_violation() -> None:
    seen = {"student_section_enrollments_view.locations_abbreviation": ["SPARK"]}
    assert sentinel.violations(seen) == [
        "student_section_enrollments_view.locations_abbreviation: 'SPARK' is "
        "not a sandbox school"
    ]


def test_seeing_nothing_proves_nothing() -> None:
    # A deployment that denies everyone, or a query that silently returns
    # nothing, would otherwise pass: no values means no violations.
    seen = {"staff_directory.work_email": [None], "staff_pii.personal_email": []}
    assert sentinel.violations(seen) == [
        "staff_directory.work_email returned no values, so nothing was checked",
        "staff_pii.personal_email returned no values, so nothing was checked",
    ]


def test_every_member_checked_has_a_rule() -> None:
    assert set(sentinel.MEMBERS) == set(sentinel.EMAIL_MEMBERS) | set(
        sentinel.SCHOOL_MEMBERS
    )


def test_the_checked_members_exist_in_the_catalog() -> None:
    import json
    from pathlib import Path

    catalog = json.loads(Path("docs/reference/cube-catalog-meta.json").read_text())
    members = {d["name"] for cube in catalog["cubes"] for d in cube["dimensions"]}
    assert set(sentinel.MEMBERS) <= members


def test_main_names_the_missing_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(sentinel.REST_URL, raising=False)
    monkeypatch.delenv(sentinel.API_SECRET, raising=False)
    with pytest.raises(SystemExit, match=sentinel.REST_URL):
        sentinel.main([])

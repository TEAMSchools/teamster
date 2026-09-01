import pytest

from teamster.libraries.iready.subjects import (
    is_legacy_year,
    partition_subject,
    remote_subject_token,
)


@pytest.mark.parametrize(
    ("academic_year", "expected"),
    [
        ("2020", True),
        ("2024", True),
        ("2025", True),
        ("2026", False),
        ("2027", False),
        ("Current_Year", False),
    ],
)
def test_is_legacy_year(academic_year, expected):
    assert is_legacy_year(academic_year) is expected


@pytest.mark.parametrize(
    ("subject", "academic_year", "expected"),
    [
        ("ela", "2025", "ela"),
        ("ela", "2026", "reading"),
        ("ela", "Current_Year", "reading"),
        ("math", "2025", "math"),
        ("math", "2026", "math"),
    ],
)
def test_remote_subject_token(subject, academic_year, expected):
    assert (
        remote_subject_token(subject=subject, academic_year=academic_year) == expected
    )


@pytest.mark.parametrize(
    ("remote_token", "academic_year", "expected"),
    [
        ("ela", "2025", "ela"),
        ("reading", "Current_Year", "ela"),
        ("reading", "2026", "ela"),
        ("math", "Current_Year", "math"),
        ("ela", "Current_Year", "ela"),
    ],
)
def test_partition_subject(remote_token, academic_year, expected):
    assert (
        partition_subject(remote_token=remote_token, academic_year=academic_year)
        == expected
    )


def test_round_trip_is_stable_for_current_era():
    token = remote_subject_token(subject="ela", academic_year="Current_Year")

    assert partition_subject(remote_token=token, academic_year="Current_Year") == "ela"

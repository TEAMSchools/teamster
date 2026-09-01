import pytest

from teamster.libraries.iready.subjects import (
    iready_remote_file_regex,
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


CURRENT_REGEX = "current-regex"
LEGACY_REGEX = "legacy-regex"


def test_iready_remote_file_regex_uses_legacy_regex_for_a_legacy_year():
    result = iready_remote_file_regex(
        remote_file_regex=CURRENT_REGEX,
        legacy_remote_file_regex=LEGACY_REGEX,
        academic_year="2025",
    )

    assert result == LEGACY_REGEX


def test_iready_remote_file_regex_falls_back_to_current_regex_when_no_legacy_given():
    result = iready_remote_file_regex(
        remote_file_regex=CURRENT_REGEX,
        legacy_remote_file_regex=None,
        academic_year="2025",
    )

    assert result == CURRENT_REGEX


@pytest.mark.parametrize("academic_year", ["2026", "Current_Year"])
def test_iready_remote_file_regex_uses_current_regex_for_the_rename_year_and_onward(
    academic_year,
):
    """Regression guard for keying era off "latest partition" instead of a
    fixed fiscal year.

    `2026` is FY2027, the first year with the new filenames, but it will not
    always be the newest partition — next July it is archived while still
    carrying the new names. If era selection were ever re-coupled to
    "Current_Year" / "is this the last partition" instead of `is_legacy_year`,
    this call (which only ever sees the academic year, never partition
    recency) would keep returning the correct answer and this test would still
    catch a regression made anywhere else, because the function's only input
    is the academic year itself.
    """
    result = iready_remote_file_regex(
        remote_file_regex=CURRENT_REGEX,
        legacy_remote_file_regex=LEGACY_REGEX,
        academic_year=academic_year,
    )

    assert result == CURRENT_REGEX

import re

import pytest
from dagster import MultiPartitionKey

from teamster.libraries.sftp.assets import compose_regex

CURRENT_REGEXES = {
    "personalized_instruction_summary": (
        r"personalized_instruction_summary_(?P<subject>ela|math|reading)"
        r"_CONFIDENTIAL\.csv"
    ),
    "personalized_instruction_by_lesson": (
        r"(personalized|iready)_instruction_by_lesson_"
        r"(?P<subject>ela|math|reading)(_CONFIDENTIAL)?\.csv"
    ),
    "instruction_by_lesson": (
        r"iready_pro_instruction_by_lesson_(?P<subject>ela|math|reading)"
        r"_CONFIDENTIAL\.csv"
    ),
    "diagnostic_results": (
        r"i-ready_inform_results_(?P<subject>ela|math|reading)"
        r"(_english)?_CONFIDENTIAL\.csv"
    ),
}

LEGACY_REGEXES = {
    "personalized_instruction_summary": (
        r"personalized_instruction_summary_(?P<subject>ela|math)_CONFIDENTIAL\.csv"
    ),
    "personalized_instruction_by_lesson": (
        r"(personalized|iready)_instruction_by_lesson_"
        r"(?P<subject>ela|math)(_CONFIDENTIAL)?\.csv"
    ),
    "instruction_by_lesson": (
        r"iready_pro_instruction_by_lesson_(?P<subject>ela|math)_CONFIDENTIAL\.csv"
    ),
    "diagnostic_results": (
        r"diagnostic_results_(?P<subject>ela|math)(_CONFIDENTIAL)?\.csv"
    ),
}

# filenames verified on the i-Ready SFTP on 2026-09-01
CURRENT_FILENAMES = {
    ("personalized_instruction_summary", "ela"): (
        "personalized_instruction_summary_reading_CONFIDENTIAL.csv"
    ),
    ("personalized_instruction_summary", "math"): (
        "personalized_instruction_summary_math_CONFIDENTIAL.csv"
    ),
    ("personalized_instruction_by_lesson", "ela"): (
        "iready_instruction_by_lesson_reading_CONFIDENTIAL.csv"
    ),
    ("personalized_instruction_by_lesson", "math"): (
        "iready_instruction_by_lesson_math_CONFIDENTIAL.csv"
    ),
    ("instruction_by_lesson", "ela"): (
        "iready_pro_instruction_by_lesson_reading_CONFIDENTIAL.csv"
    ),
    ("instruction_by_lesson", "math"): (
        "iready_pro_instruction_by_lesson_math_CONFIDENTIAL.csv"
    ),
    ("diagnostic_results", "ela"): (
        "i-ready_inform_results_reading_english_CONFIDENTIAL.csv"
    ),
    ("diagnostic_results", "math"): "i-ready_inform_results_math_CONFIDENTIAL.csv",
}

LEGACY_FILENAMES = {
    ("personalized_instruction_summary", "ela"): (
        "personalized_instruction_summary_ela_CONFIDENTIAL.csv"
    ),
    ("personalized_instruction_summary", "math"): (
        "personalized_instruction_summary_math_CONFIDENTIAL.csv"
    ),
    ("diagnostic_results", "ela"): "diagnostic_results_ela_CONFIDENTIAL.csv",
    ("diagnostic_results", "math"): "diagnostic_results_math_CONFIDENTIAL.csv",
}

# stale pre-rename files the vendor left in Current_Year on 2026-07-18
STALE_CURRENT_YEAR_FILENAMES = [
    "diagnostic_results_ela_CONFIDENTIAL.csv",
    "diagnostic_results_math_CONFIDENTIAL.csv",
    "personalized_instruction_summary_ela_CONFIDENTIAL.csv",
    "iready_pro_instruction_by_lesson_ela_CONFIDENTIAL.csv",
]


def _composed(regex, subject, academic_year):
    from teamster.libraries.iready.subjects import remote_subject_token

    return compose_regex(
        regexp=regex,
        partition_key=MultiPartitionKey(
            {
                "academic_year": academic_year,
                "subject": remote_subject_token(
                    subject=subject, academic_year=academic_year
                ),
            }
        ),
    )


@pytest.mark.parametrize(("asset_name", "subject"), sorted(CURRENT_FILENAMES))
def test_current_era_regex_matches_live_filename(asset_name, subject):
    composed = _composed(CURRENT_REGEXES[asset_name], subject, "Current_Year")

    assert re.fullmatch(composed, CURRENT_FILENAMES[(asset_name, subject)]) is not None


@pytest.mark.parametrize(("asset_name", "subject"), sorted(LEGACY_FILENAMES))
def test_legacy_era_regex_matches_archive_filename(asset_name, subject):
    composed = _composed(LEGACY_REGEXES[asset_name], subject, "2025")

    assert re.fullmatch(composed, LEGACY_FILENAMES[(asset_name, subject)]) is not None


@pytest.mark.parametrize("stale_filename", STALE_CURRENT_YEAR_FILENAMES)
@pytest.mark.parametrize("subject", ["ela", "math"])
def test_current_era_regex_never_matches_a_stale_file(stale_filename, subject):
    """The July 2026 leftovers must be unmatchable in the current era.

    This is the bug: a stale FY26 file matching a FY27 partition is how 3,933
    rows of last year's data ended up labelled as this year's.
    """
    for regex in CURRENT_REGEXES.values():
        composed = _composed(regex, subject, "Current_Year")

        assert re.fullmatch(composed, stale_filename) is None

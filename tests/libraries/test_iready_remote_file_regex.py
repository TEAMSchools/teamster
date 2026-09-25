import importlib
import re

import pytest
from dagster import MultiPartitionKey

from teamster.libraries.iready.subjects import remote_subject_token
from teamster.libraries.sftp.assets import compose_regex

# Import the i-Ready asset SUBMODULE directly, not the `<location>.iready`
# package. That package's `__init__.py` does
# `from .assets import assets` (a list of AssetsDefinition), which reassigns
# the package's `assets` ATTRIBUTE to that list -- so `import a.b.iready.assets
# as x` (attribute-chain resolution) or `from a.b.iready import assets` would
# both silently hand back the list, not this module. `importlib.import_module`
# goes through `sys.modules` by dotted name instead of attribute lookup, so it
# is not fooled by the shadowing.
#
# `kippmiami.iready.assets` and `kippnewark.iready.assets` import cleanly on
# their own (verified) -- unlike their code locations' `definitions` modules,
# which fail in this environment on missing Focus/dlt credentials.
ASSET_MODULES = {
    "kippmiami": importlib.import_module(
        "teamster.code_locations.kippmiami.iready.assets"
    ),
    "kippnewark": importlib.import_module(
        "teamster.code_locations.kippnewark.iready.assets"
    ),
}

LOCATIONS = list(ASSET_MODULES)

ASSET_NAMES = [
    "personalized_instruction_summary",
    "personalized_instruction_by_lesson",
    "instruction_by_lesson",
    "diagnostic_results",
]


def _metadata_by_asset_name(location: str) -> dict:
    """The shipped `remote_file_regex` / `legacy_remote_file_regex` metadata
    for every i-Ready asset in a code location, keyed by the asset key's last
    segment (`personalized_instruction_by_lesson`, not the Python variable
    name `instruction_by_lesson` some of these are assigned to).
    """
    module = ASSET_MODULES[location]

    return {
        assets_def.key.path[-1]: assets_def.metadata_by_key[assets_def.key]
        for assets_def in module.assets
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


def _production_style_match(
    dir_regex: str, file_regex: str, subject: str, academic_year: str, filename: str
):
    """Match a filename the same way `build_sftp_file_asset` does: compose
    dir + file regex together and `re.search` a full remote path, not
    `re.fullmatch` a bare filename (see `src/teamster/libraries/sftp/assets.py`
    around the `remote_dir_regex_composed`/`remote_file_regex_composed`
    `re.search` call).
    """
    partition_key = MultiPartitionKey(
        {
            "academic_year": academic_year,
            "subject": remote_subject_token(
                subject=subject, academic_year=academic_year
            ),
        }
    )

    dir_composed = compose_regex(regexp=dir_regex, partition_key=partition_key)
    file_composed = compose_regex(regexp=file_regex, partition_key=partition_key)

    full_path = f"{dir_composed}/{filename}"

    return re.search(pattern=f"{dir_composed}/{file_composed}", string=full_path)


@pytest.mark.parametrize("location", LOCATIONS)
@pytest.mark.parametrize(("asset_name", "subject"), sorted(CURRENT_FILENAMES))
def test_current_era_regex_matches_live_filename(location, asset_name, subject):
    metadata = _metadata_by_asset_name(location)[asset_name]

    match = _production_style_match(
        dir_regex=metadata["remote_dir_regex"],
        file_regex=metadata["remote_file_regex"],
        subject=subject,
        academic_year="Current_Year",
        filename=CURRENT_FILENAMES[(asset_name, subject)],
    )

    assert match is not None


@pytest.mark.parametrize("location", LOCATIONS)
@pytest.mark.parametrize(("asset_name", "subject"), sorted(LEGACY_FILENAMES))
def test_legacy_era_regex_matches_archive_filename(location, asset_name, subject):
    metadata = _metadata_by_asset_name(location)[asset_name]

    match = _production_style_match(
        dir_regex=metadata["remote_dir_regex"],
        file_regex=metadata["legacy_remote_file_regex"],
        subject=subject,
        academic_year="2025",
        filename=LEGACY_FILENAMES[(asset_name, subject)],
    )

    assert match is not None


@pytest.mark.parametrize("location", LOCATIONS)
@pytest.mark.parametrize("asset_name", ASSET_NAMES)
@pytest.mark.parametrize("stale_filename", STALE_CURRENT_YEAR_FILENAMES)
@pytest.mark.parametrize("subject", ["ela", "math"])
def test_current_era_regex_never_matches_a_stale_file(
    location, asset_name, stale_filename, subject
):
    """The July 2026 leftovers must be unmatchable in the current era.

    This is the bug: a stale FY26 file matching a FY27 partition is how 3,933
    rows of last year's data ended up labelled as this year's.
    """
    metadata = _metadata_by_asset_name(location)[asset_name]

    match = _production_style_match(
        dir_regex=metadata["remote_dir_regex"],
        file_regex=metadata["remote_file_regex"],
        subject=subject,
        academic_year="Current_Year",
        filename=stale_filename,
    )

    assert match is None

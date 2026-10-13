import re

from teamster.code_locations.kippnewark.amplify.mclass.sftp.assets import (
    archive_remote_dir,
    pm_student_summary,
)
from teamster.libraries.sftp.assets import compose_regex


def test_archive_remote_dir_maps_school_year_to_archive_folder():
    assert archive_remote_dir("PM")("2025-2026") == "/25-26/PM"
    assert archive_remote_dir("BM")("2024-2025") == "/24-25/BM"


def test_archived_pm_path_matches_composed_regex():
    """Filename shape verified live on 2026-09-22 under /25-26/PM."""
    metadata = pm_student_summary.metadata_by_key[pm_student_summary.key]
    file_regex = compose_regex(
        regexp=metadata["remote_file_regex"], partition_key="2025-2026"
    )
    archive_dir = archive_remote_dir("PM")("2025-2026")

    assert re.search(
        f"{archive_dir}/{file_regex}", "/25-26/PM/dibels8_PM_2025-2026_20260921.csv"
    )
    # the sensor's anchored match on the current directory must not see it
    assert not re.match(
        f"{metadata['remote_dir_regex']}/{metadata['remote_file_regex']}",
        "/25-26/PM/dibels8_PM_2025-2026_20260921.csv",
    )

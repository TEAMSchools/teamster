import hashlib
from datetime import datetime, timedelta, timezone

from cube_validation import report, saved
from cube_validation.moment import Build

END = datetime(2026, 10, 28, 21, 35, tzinfo=timezone.utc)
BUILD = Build(END - timedelta(minutes=1), END, "job")


def test_a_table_is_named_by_view_moment_and_comparison():
    sha = hashlib.sha256(b"ada-region").hexdigest()[:8]

    assert saved.table_id("v", BUILD, "ada-region") == (
        "teamster-332318.cube_validation_scratch."
        f"v__2026_10_28t213500z__ada_region_{sha}"
    )
    assert saved.table_sql(saved.table_id("v", BUILD, "ada-region")).startswith(
        "`teamster-332318`.`cube_validation_scratch`.`v__"
    )


def test_ids_that_differ_only_in_punctuation_get_different_tables():
    assert saved.table_id("v", BUILD, "a-b") != saved.table_id("v", BUILD, "a_b")


def test_labels_are_what_bigquery_takes():
    got = saved.labels("v", BUILD, "Ada Region", "f" * 64)

    assert got == {
        "view": "v",
        "moment": "2026-10-28t213500z",
        "comparison": "ada_region",
        "fingerprint": "f" * 32,
    }


def test_a_label_value_is_cut_at_63_characters():
    assert len(saved.labels("v" * 80, BUILD, "c", "f" * 64)["view"]) == 63


def test_the_run_folder_and_the_tables_share_one_stamp():
    assert report.run_stamp(BUILD) == "2026-10-28T213500Z"

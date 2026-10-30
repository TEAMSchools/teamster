from __future__ import annotations

from teamster.cube_sandbox import checks

SNAP = {"tables": {"dim_x": {"a": {"type": "STRING", "nullable": True}}}}


def test_a_consistent_pair_reports_nothing() -> None:
    assert checks.missing_columns({"dim_x": {"a"}}, SNAP) == []


def test_a_model_column_absent_from_the_snapshot_is_named() -> None:
    # The check compares model and snapshot at the SAME commit, so this is
    # what a model change outrunning the snapshot looks like.
    missing = checks.missing_columns({"dim_x": {"a", "b"}}, SNAP)
    assert missing == ["dim_x.b"]


def test_a_model_table_absent_from_the_snapshot_does_not_raise() -> None:
    # A KeyError here would report a crash instead of the real problem.
    assert checks.missing_columns({"dim_y": {"z"}}, SNAP) == ["dim_y.z"]


def test_missing_tables_are_named_separately_from_missing_columns() -> None:
    # A whole table missing is a different fix from one column missing — the
    # snapshot refresh never saw the table at all — so the report says which.
    assert checks.missing_tables({"dim_y", "dim_x"}, SNAP) == ["dim_y"]
    assert checks.missing_tables({"dim_x"}, SNAP) == []


def test_the_live_model_and_snapshot_agree() -> None:
    # The assertion the CI workflow makes. It reads only committed files, so
    # it cannot cry wolf on a moving input.
    assert checks.run(checks.CUBE_ROOT) == []


def test_the_committed_manifest_is_in_sync_with_its_generator() -> None:
    # coverage_manifest.yml is generated and committed. Nothing else notices
    # if the two drift, and every downstream coverage result is then asserted
    # against a contract that no longer matches the model.
    assert checks.stale_manifest() is None

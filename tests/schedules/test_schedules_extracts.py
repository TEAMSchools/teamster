def test_clever_extracts_run_in_process():
    from teamster.code_locations.kipptaf.extracts.jobs import (
        clever_extract_asset_job,
    )

    executor_def = clever_extract_asset_job.executor_def
    assert executor_def is not None
    assert executor_def.name == "in_process"

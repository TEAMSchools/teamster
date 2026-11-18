def test_tableau_extract_refreshes_run_in_process():
    from teamster.code_locations.kipptaf.tableau.schedules import (
        extract_refresh_schedules,
    )

    assert extract_refresh_schedules
    for s in extract_refresh_schedules:
        job = s.job
        assert job.name == s.name.removesuffix("_schedule") + "_asset_job"
        assert job.executor_def is not None
        assert job.executor_def.name == "in_process"

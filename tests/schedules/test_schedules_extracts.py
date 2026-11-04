def test_clever_extracts_run_multiprocess_with_more_memory():
    from dagster_k8s.job import get_user_defined_k8s_config

    from teamster.code_locations.kipptaf.extracts.jobs import (
        clever_extract_asset_job,
    )

    executor_def = clever_extract_asset_job.executor_def
    assert executor_def is not None
    assert executor_def.name == "multiprocess"

    # parse the tag the way the run launcher does
    config = get_user_defined_k8s_config(clever_extract_asset_job.tags or {})
    assert config.container_config["resources"] == {
        "requests": {"memory": "6.0Gi"},
        "limits": {"memory": "7.0Gi"},
    }

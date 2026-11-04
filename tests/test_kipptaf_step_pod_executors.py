"""Jobs that run their steps inside the run pod instead of one step pod each.

GKE preempts pods on nodes it adds during pod bursts (#6225), so these jobs
avoid step pods.
"""


def test_google_forms_responses_sensor_runs_in_process():
    from teamster.code_locations.kipptaf.google.forms.sensors import (
        google_forms_responses_asset_job,
        google_forms_responses_sensor,
    )

    assert (
        google_forms_responses_sensor.job_name
        == "kipptaf__google__forms__responses_asset_job"
    )
    assert google_forms_responses_asset_job.executor_def is not None
    assert google_forms_responses_asset_job.executor_def.name == "in_process"


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
        "requests": {"memory": "3.5Gi"},
        "limits": {"memory": "4.0Gi"},
    }

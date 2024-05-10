from dagster import EnvVar, materialize

from teamster.core.resources import get_io_manager_gcs_file
from teamster.kipptaf.powerschool.enrollment.assets import foo
from teamster.kipptaf.powerschool.enrollment.resources import (
    PowerSchoolEnrollmentResource,
)


def test_asset():
    result = materialize(
        assets=[foo],
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_file("staging"),
            "ps_enrollment": PowerSchoolEnrollmentResource(
                api_key=EnvVar("POWERSCHOOL_ENROLLMENT_API_KEY")
            ),
        },
    )

    assert result.success
    assert (
        result.get_asset_materialization_events()[0]
        .event_specific_data.materialization.metadata["records"]  # type: ignore
        .value
        > 0
    )
    assert result.get_asset_check_evaluations()[0].metadata.get("extras").text == ""

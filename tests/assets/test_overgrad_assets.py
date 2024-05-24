from dagster import EnvVar, materialize

from teamster.core.resources import get_io_manager_gcs_avro
from teamster.overgrad.assets import (
    admissions,
    custom_fields,
    followings,
    schools,
    students,
    universities,
)
from teamster.overgrad.resources import OvergradResource


def _test_asset(asset):
    result = materialize(
        assets=[asset],
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_avro("test"),
            "overgrad": OvergradResource(
                api_key=EnvVar("OVERGRAD_API_KEY"), page_limit=100
            ),
        },
    )

    assert result.success
    assert (
        result.get_asset_materialization_events()[0]
        .event_specific_data.materialization.metadata["row_count"]  # pyright: ignore[reportOperatorIssue, reportAttributeAccessIssue, reportOptionalMemberAccess]
        .value
        > 0
    )
    assert result.get_asset_check_evaluations()[0].metadata.get("extras").text == ""  # pyright: ignore[reportOptionalMemberAccess]


def test_schools():
    _test_asset(asset=schools)


def test_admissions():
    _test_asset(asset=admissions)


def test_custom_fields():
    _test_asset(asset=custom_fields)


def test_followings():
    _test_asset(asset=followings)


def test_students():
    _test_asset(asset=students)


def test_universities():
    _test_asset(asset=universities)

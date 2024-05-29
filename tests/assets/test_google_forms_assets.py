import random

from dagster import AssetsDefinition, DagsterInstance, materialize

from teamster.core.resources import get_io_manager_gcs_avro
from teamster.kipptaf.google.forms.assets import form, responses
from teamster.kipptaf.resources import GOOGLE_FORMS_RESOURCE


def _test_asset(asset: AssetsDefinition, partition_key: str | None = None):
    instance = DagsterInstance.from_config(
        config_dir=".dagster/home", config_filename="dagster-cloud.yaml"
    )

    if partition_key is None:
        partition_keys = asset.partitions_def.get_partition_keys(  # pyright: ignore[reportOptionalMemberAccess]
            dynamic_partitions_store=instance
        )

        partition_key = partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))]

    result = materialize(
        assets=[asset],
        instance=instance,
        partition_key=partition_key,
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_avro("test"),
            "google_forms": GOOGLE_FORMS_RESOURCE,
        },
    )

    assert result.success
    assert (
        result.get_asset_materialization_events()[0]
        .event_specific_data.materialization.metadata["record_count"]  # pyright: ignore[reportOperatorIssue, reportAttributeAccessIssue, reportOptionalMemberAccess]
        .value
        > 0
    )
    assert result.get_asset_check_evaluations()[0].metadata.get("extras").text == ""  # pyright: ignore[reportOptionalMemberAccess]


def test_asset_google_forms_form():
    _test_asset(asset=form)


def test_asset_google_forms_responses():
    _test_asset(
        asset=responses,
        # trunk-ignore(gitleaks/generic-api-key)
        partition_key="15Iq_dMeOmURb68Bg8Uc6j-Fco4N2wix7D8YFfSdCKPE",
    )

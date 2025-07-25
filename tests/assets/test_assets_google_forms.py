import random

from dagster import (
    AssetsDefinition,
    DagsterInstance,
    PartitionsDefinition,
    TextMetadataValue,
    materialize,
)
from dagster._core.events import StepMaterializationData
from dagster_shared import check

from teamster.core.resources import GOOGLE_FORMS_RESOURCE, get_io_manager_gcs_avro


def _test_asset(asset: AssetsDefinition, partition_key: str | None = None):
    instance = DagsterInstance.from_config(
        config_dir=".dagster/home", config_filename="dagster-cloud.yaml"
    )

    if partition_key is None:
        partitions_def = check.inst(
            obj=asset.partitions_def, ttype=PartitionsDefinition
        )
        partition_keys = partitions_def.get_partition_keys(
            dynamic_partitions_store=instance
        )

        partition_key = partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))]

    result = materialize(
        assets=[asset],
        instance=instance,
        partition_key=partition_key,
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_avro(
                code_location="test", test=True
            ),
            "google_forms": GOOGLE_FORMS_RESOURCE,
        },
    )

    assert result.success

    asset_materialization_event = result.get_asset_materialization_events()[0]
    event_specific_data = check.inst(
        asset_materialization_event.event_specific_data, StepMaterializationData
    )
    records = check.inst(
        event_specific_data.materialization.metadata["record_count"].value, int
    )
    assert records > 0

    extras = check.inst(
        obj=result.get_asset_check_evaluations()[0].metadata.get("extras"),
        ttype=TextMetadataValue,
    )
    assert extras.text == ""


def test_asset_google_forms_form():
    from teamster.code_locations.kipptaf._google.forms.assets import form

    _test_asset(
        # trunk-ignore(pyright/reportArgumentType)
        asset=form,
        # trunk-ignore(gitleaks/generic-api-key)
        partition_key="1x8uQ_pIkW8nXU-HpZb6OEjMBjf-16CKbFRGnfiLd2rE",
    )


def test_asset_google_forms_responses():
    from teamster.code_locations.kipptaf._google.forms.assets import responses

    _test_asset(
        # trunk-ignore(pyright/reportArgumentType)
        asset=responses,
        # trunk-ignore(gitleaks/generic-api-key)
        partition_key="15Iq_dMeOmURb68Bg8Uc6j-Fco4N2wix7D8YFfSdCKPE",
    )

import random

from dagster import TextMetadataValue, _check, instance_for_test, materialize
from dagster._core.events import StepMaterializationData

from teamster.code_locations.kipptaf.alchemer.assets import (
    survey,
    survey_campaign,
    survey_question,
    survey_response,
)
from teamster.code_locations.kipptaf.resources import ALCHEMER_RESOURCE
from teamster.libraries.core.resources import get_io_manager_gcs_avro

SURVEY_IDS = [
    "2934233",
    "3167842",
    "3167903",
    "3211265",
    "3242248",
    "3370039",
    "3511436",
    "3727563",
    "3767678",
    "3774202",
    "3779180",
    "3779230",
    "4000821",
    "4031194",
    "4160102",
    "4251844",
    "4561288",
    "4561325",
    "4839791",
    "4843086",
    "4859726",
    "5300913",
    "5351760",
    "5560557",
    "6330385",
    "6580731",
    "6686058",
    "6734664",
    "6829997",
    "6997086",
    "7151740",
    "7196293",
    "7253288",
    "7257415",
    "3108476",
    "5593585",
    "7257431",
    "3946606",
    "7257383",
]


def _test_asset(asset, partition_key=None):
    if partition_key is None:
        partition_key = SURVEY_IDS[random.randint(a=0, b=(len(SURVEY_IDS) - 1))]

    with instance_for_test() as instance:
        instance.add_dynamic_partitions(
            partitions_def_name=asset.partitions_def.name,
            partition_keys=SURVEY_IDS,
        )

        result = materialize(
            assets=[asset],
            instance=instance,
            partition_key=partition_key,
            resources={
                "io_manager_gcs_avro": get_io_manager_gcs_avro(
                    code_location="test", test=True
                ),
                "alchemer": ALCHEMER_RESOURCE,
            },
        )

    assert result.success
    asset_materialization_event = result.get_asset_materialization_events()[0]
    event_specific_data = _check.inst(
        asset_materialization_event.event_specific_data, StepMaterializationData
    )
    records = _check.inst(
        event_specific_data.materialization.metadata["records"].value, int
    )
    assert records > 0
    extras = _check.inst(
        obj=result.get_asset_check_evaluations()[0].metadata.get("extras"),
        ttype=TextMetadataValue,
    )
    assert extras.text == ""


def test_asset_alchemer_survey():
    _test_asset(asset=survey)


def test_asset_alchemer_survey_question():
    _test_asset(asset=survey_question, partition_key="7151740")


def test_asset_alchemer_survey_campaign():
    _test_asset(asset=survey_campaign)


def test_asset_alchemer_survey_response():
    _test_asset(asset=survey_response, partition_key="4561325_1656651600")

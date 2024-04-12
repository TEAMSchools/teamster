import random

from dagster import instance_for_test, materialize

from teamster.core.resources import get_io_manager_gcs_avro
from teamster.kipptaf.alchemer.assets import (
    survey,
    survey_campaign,
    survey_question,
    survey_response,
)
from teamster.kipptaf.resources import ALCHEMER_RESOURCE

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


def _test_asset(asset, partition_keys):
    with instance_for_test() as instance:
        instance.add_dynamic_partitions(
            partitions_def_name=asset.partitions_def.name,  # type: ignore
            partition_keys=partition_keys,
        )

        result = materialize(
            assets=[asset],
            instance=instance,
            partition_key=partition_keys[
                random.randint(a=0, b=(len(partition_keys) - 1))
            ],
            resources={
                "io_manager_gcs_avro": get_io_manager_gcs_avro("staging"),
                "alchemer": ALCHEMER_RESOURCE,
            },
        )

    assert result.success
    assert (
        result.get_asset_materialization_events()[0]
        .event_specific_data.materialization.metadata["record_count"]  # type: ignore
        .value
        > 0
    )
    assert result.get_asset_check_evaluations()[0].metadata.get("extras").text == ""


def test_asset_alchemer_survey():
    _test_asset(asset=survey, partition_keys=SURVEY_IDS)


def test_asset_alchemer_survey_campaign():
    _test_asset(asset=survey_campaign, partition_keys=SURVEY_IDS)


def test_asset_alchemer_survey_question():
    _test_asset(asset=survey_question, partition_keys=SURVEY_IDS)


def test_asset_alchemer_survey_response():
    _test_asset(
        asset=survey_response,
        partition_keys=[
            f"{s}_0.0"
            for s in [
                # "4561325",  # 60855
                # "4561288",  # 15955
                # "5300913",  # 8688
                # "3767678",  # 7583
                # "3242248",  # 4995
                # "6829997",  # 4604
                # "6330385",  # 4460
                # "6580731",  # 3089
                # "4000821",  # 2833
                # "3108476",  # 1924
                # "5593585",  # 1444
                # "4251844",  # 1383
                # "3211265",  # 1317
                # "3779230",  # 797
                # "5560557",  # 786
                # "2934233",  # 731
                # "3370039",  # 700
                "7151740",  # 495
                # "3167842",  # 334
                # "4160102",  # 299
                # "6734664",  # 133
                # "4839791",  # 93
                "6997086",  # 92
                # "3167903",  # 9
                # "4843086",  # 8
                # "3511436",  # 7
                "7196293",  # 6
                # "7253288",  # 6
                # "3727563",  # 4
                # "3774202",  # 2
                # "7257415",  # 1
                # "4031194",  # 750
            ]
        ],
    )

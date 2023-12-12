import random

import pendulum
from dagster import AssetsDefinition, instance_for_test, materialize

from teamster.core.resources import get_io_manager_gcs_avro
from teamster.kipptaf.alchemer.assets import (
    survey,
    survey_campaign,
    survey_question,
    survey_response,
)
from teamster.kipptaf.resources import ALCHEMER_RESOURCE

SURVEY_IDS = ["7151740"]


def _test_asset(asset: AssetsDefinition, partition_keys):
    with instance_for_test() as instance:
        instance.add_dynamic_partitions(
            partitions_def_name=asset.partitions_def.name, partition_keys=partition_keys
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
        .event_specific_data.materialization.metadata["record_count"]
        .value
        > 0
    )


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
            f"{s}_{pendulum.datetime(year=2023, month=7, day=1).timestamp()}"
            for s in SURVEY_IDS
        ],
    )

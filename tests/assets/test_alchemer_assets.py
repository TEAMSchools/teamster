import random

import pendulum
from dagster import AssetsDefinition, EnvVar, instance_for_test, materialize
from dagster_gcp import GCSResource

from teamster import GCS_PROJECT_NAME
from teamster.core.google.storage.io_manager import GCSIOManager
from teamster.kipptaf.alchemer.assets import (
    survey,
    survey_campaign,
    survey_question,
    survey_response,
)
from teamster.kipptaf.alchemer.resources import AlchemerResource

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
                "io_manager_gcs_avro": GCSIOManager(
                    gcs=GCSResource(project=GCS_PROJECT_NAME),
                    gcs_bucket="teamster-staging",
                    object_type="avro",
                ),
                "alchemer": AlchemerResource(
                    api_token=EnvVar("ALCHEMER_API_TOKEN"),
                    api_token_secret=EnvVar("ALCHEMER_API_TOKEN_SECRET"),
                    api_version="v5",
                ),
            },
        )

    assert result.success

    event = result.get_asset_materialization_events()[0]

    assert event.event_specific_data.materialization.metadata["record_count"].value > 0


def test_alchemer_asset_survey():
    _test_asset(asset=survey, partition_keys=SURVEY_IDS)


def test_alchemer_asset_survey_campaign():
    _test_asset(asset=survey_campaign, partition_keys=SURVEY_IDS)


def test_alchemer_asset_survey_question():
    _test_asset(asset=survey_question, partition_keys=SURVEY_IDS)


def test_alchemer_asset_survey_response():
    _test_asset(
        asset=survey_response,
        partition_keys=[
            f"{s}_{pendulum.datetime(year=2023, month=7, day=1).timestamp()}"
            for s in SURVEY_IDS
        ],
    )

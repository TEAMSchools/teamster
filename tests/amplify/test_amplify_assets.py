import random

from dagster import EnvVar, materialize
from dagster_gcp import GCSResource

from teamster import GCS_PROJECT_NAME
from teamster.core.google.storage.io_manager import GCSIOManager
from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.kipptaf.amplify.assets import build_mclass_asset
from teamster.kipptaf.amplify.resources import MClassResource
from teamster.staging import LOCAL_TIMEZONE


def _test_asset(asset_name, dyd_payload, partition_start_date):
    asset = build_mclass_asset(
        name=asset_name,
        dyd_payload=dyd_payload,
        partitions_def=FiscalYearPartitionsDefinition(
            start_date=partition_start_date, timezone=LOCAL_TIMEZONE.name, start_month=7
        ),
    )

    partition_keys = asset.partitions_def.get_partition_keys()

    result = materialize(
        assets=[asset],
        partition_key=partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))],
        resources={
            "io_manager_gcs_avro": GCSIOManager(
                gcs=GCSResource(project=GCS_PROJECT_NAME),
                gcs_bucket="teamster-staging",
                object_type="avro",
            ),
            "mclass": MClassResource(
                username=EnvVar("AMPLIFY_USERNAME"), password=EnvVar("AMPLIFY_PASSWORD")
            ),
        },
    )

    assert result.success


def test_mclass_asset_benchmark_student_summary():
    _test_asset(
        asset_name="benchmark_student_summary",
        partition_start_date="2022-07-01",
        dyd_payload={
            "dyd_results": "BM",
            "accounts": "1300588536",
            "districts": "1300588535",
            "roster_option": "2",  # On Test Day
            "dyd_assessments": "7_D8",  # DIBELS 8th Edition
            "tracking_id": None,
        },
    )


def test_mclass_asset_pm_student_summary():
    _test_asset(
        asset_name="pm_student_summary",
        partition_start_date="2022-07-01",
        dyd_payload={
            "dyd_results": "PM",
            "accounts": "1300588536",
            "districts": "1300588535",
            "roster_option": "2",  # On Test Day
            "dyd_assessments": "7_D8",  # DIBELS 8th Edition
            "tracking_id": None,
        },
    )

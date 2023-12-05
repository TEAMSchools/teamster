import random

from dagster import (
    AssetsDefinition,
    DailyPartitionsDefinition,
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    materialize,
)
from dagster_gcp import GCSResource

from teamster import GCS_PROJECT_NAME
from teamster.core.deanslist.assets import (
    build_deanslist_multi_partition_asset,
    build_deanslist_static_partition_asset,
)
from teamster.core.deanslist.resources import DeansListResource
from teamster.core.google.storage.io_manager import GCSIOManager
from teamster.staging import LOCAL_TIMEZONE

STATIC_PARTITIONS_DEF = StaticPartitionsDefinition(
    ["121", "122", "123", "124", "125", "127", "128", "129", "378", "380", "522", "523"]
)


def _test_asset(asset: AssetsDefinition):
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
            "deanslist": DeansListResource(
                subdomain="kippnj",
                api_key_map="/etc/secret-volume/deanslist_api_key_map_yaml",
            ),
        },
    )

    assert result.success


def test_deanslist_static_partition_asset():
    _test_asset(
        asset=build_deanslist_static_partition_asset(
            code_location="staging",
            partitions_def=STATIC_PARTITIONS_DEF,
            asset_name="users",
            api_version="v1",
            params={"IncludeInactive": "Y"},
        )
    )


def test_deanslist_multi_partition_asset():
    _test_asset(
        asset=build_deanslist_multi_partition_asset(
            code_location="staging",
            partitions_def=MultiPartitionsDefinition(
                partitions_defs={
                    "date": DailyPartitionsDefinition(
                        start_date="2023-03-23",
                        timezone=LOCAL_TIMEZONE.name,
                        end_offset=1,
                    ),
                    "school": STATIC_PARTITIONS_DEF,
                }
            ),
            asset_name="incidents",
            api_version="v1",
            params={
                "StartDate": "{start_date}",
                "EndDate": "{end_date}",
                "IncludeDeleted": "Y",
                "cf": "Y",
            },
        )
    )

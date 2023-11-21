from dagster import (
    AssetsDefinition,
    DailyPartitionsDefinition,
    Definitions,
    MultiPartitionKey,
    MultiPartitionsDefinition,
    Output,
    StaticPartitionsDefinition,
    asset,
    define_asset_job,
)
from dagster_gcp import GCSResource

from teamster import GCS_PROJECT_NAME
from teamster.core.google.storage.io_manager import GCSIOManager
from teamster.core.utils.functions import get_avro_record_schema


def build_test_asset_avro(name, partitions_def):
    @asset(
        key=["staging", "test", name],
        partitions_def=partitions_def,
        io_manager_key="io_manager_gcs_avro",
    )
    def _asset():
        yield Output(
            value=(
                [{"foo": "bar"}],
                get_avro_record_schema(
                    name="test",
                    fields=[
                        {"name": "foo", "type": ["null", "string"], "default": None}
                    ],
                ),
            )
        )

    return _asset


def _test(asset_def: AssetsDefinition, partition_key, expected_path):
    job_name = asset_def.key.to_python_identifier(suffix="job")

    defs = Definitions(
        assets=[asset_def],
        jobs=[define_asset_job(name=job_name, selection=[asset_def])],
        resources={
            "io_manager_gcs_avro": GCSIOManager(
                gcs=GCSResource(project=GCS_PROJECT_NAME),
                gcs_bucket="teamster-staging",
                object_type="avro",
            ),
            "io_manager_gcs_file": GCSIOManager(
                gcs=GCSResource(project=GCS_PROJECT_NAME),
                gcs_bucket="teamster-staging",
                object_type="file",
            ),
        },
    )

    result = defs.get_job_def(job_name).execute_in_process(partition_key=partition_key)

    handled_output_event = [
        e for e in result.all_node_events if e.event_type_value == "HANDLED_OUTPUT"
    ][0]

    assert (
        handled_output_event.event_specific_data.metadata["path"].value == expected_path
    )


def test_avro_multipartition_with_date_asset():
    asset_name = "avro_multipartition_with_date_asset"

    _test(
        asset_def=build_test_asset_avro(
            name=asset_name,
            partitions_def=MultiPartitionsDefinition(
                {
                    "date": DailyPartitionsDefinition(start_date="2023-01-01"),
                    "spam": StaticPartitionsDefinition(["eggs"]),
                }
            ),
        ),
        partition_key=MultiPartitionKey({"date": "2023-11-01", "spam": "eggs"}),
        expected_path=f"dagster/staging/test/{asset_name}/_dagster_partition_fiscal_year=2024/_dagster_partition_date=2023-11-01/_dagster_partition_hour=00/_dagster_partition_minute=00/_dagster_partition_spam=eggs/data",
    )


def test_avro_multipartition_asset():
    asset_name = "avro_multipartition_asset"

    _test(
        asset_def=build_test_asset_avro(
            name=asset_name,
            partitions_def=MultiPartitionsDefinition(
                {
                    "foo": StaticPartitionsDefinition(["bar"]),
                    "spam": StaticPartitionsDefinition(["eggs"]),
                }
            ),
        ),
        partition_key=MultiPartitionKey({"foo": "bar", "spam": "eggs"}),
        expected_path=f"dagster/staging/test/{asset_name}/_dagster_partition_foo=bar/_dagster_partition_spam=eggs/data",
    )


def test_avro_datetime_partition_asset():
    asset_name = "avro_datetime_partition_asset"

    _test(
        asset_def=build_test_asset_avro(
            name=asset_name,
            partitions_def=DailyPartitionsDefinition(start_date="2023-01-01"),
        ),
        partition_key="2023-11-01",
        expected_path=f"dagster/staging/test/{asset_name}/_dagster_partition_fiscal_year=2024/_dagster_partition_date=2023-11-01/_dagster_partition_hour=00/_dagster_partition_minute=00/data",
    )


def test_avro_static_partition_asset():
    asset_name = "avro_static_partition_asset"

    _test(
        asset_def=build_test_asset_avro(
            name=asset_name,
            partitions_def=StaticPartitionsDefinition(["2020"]),
        ),
        partition_key="2020",
        expected_path=f"dagster/staging/test/{asset_name}/_dagster_partition_key=2020/data",
    )

import json
import pathlib

import py_avro_schema
from dagster._core.events import HandledOutputData
from pydantic import BaseModel

from dagster import (
    AssetsDefinition,
    DailyPartitionsDefinition,
    MultiPartitionKey,
    MultiPartitionsDefinition,
    Output,
    StaticPartitionsDefinition,
    _check,
    asset,
    materialize,
)
from teamster.core.resources import get_io_manager_gcs_avro, get_io_manager_gcs_file


def build_test_asset_avro(
    name, partitions_def=None, output_schema=None, output_data=None
):
    if output_data is None:

        class TestSchema(BaseModel):
            foo: str | None = None

        output_data = [{"foo": "bar"}]
        output_schema = json.loads(py_avro_schema.generate(py_type=TestSchema))

    @asset(
        key=["staging", "test", name],
        partitions_def=partitions_def,
        io_manager_def=get_io_manager_gcs_avro(code_location="test", test=True),
    )
    def _asset():
        yield Output(value=(output_data, output_schema))

    return _asset


def build_test_asset_file(name, partitions_def=None):
    @asset(
        key=["staging", "test", name],
        partitions_def=partitions_def,
        io_manager_def=get_io_manager_gcs_file(code_location="test", test=True),
    )
    def _asset():
        path = pathlib.Path("/workspaces/teamster/env/data.avro")

        path.touch()

        yield Output(value=path)

    return _asset


def _test_asset_handle_output_path(
    asset_def: AssetsDefinition, expected_path, partition_key=None
):
    result = materialize(assets=[asset_def], partition_key=partition_key)

    handled_output_event = [
        e for e in result.all_node_events if e.event_type_value == "HANDLED_OUTPUT"
    ][0]

    event_specific_data = _check.inst(
        handled_output_event.event_specific_data, HandledOutputData
    )

    assert (event_specific_data.metadata["path"].value) == expected_path


def test_avro_handle_asset():
    asset_name = "avro_asset"

    _test_asset_handle_output_path(
        asset_def=build_test_asset_avro(name=asset_name),
        expected_path=f"dagster/staging/test/{asset_name}/data",
    )


def test_avro_handle_asset_multipartition_with_date():
    asset_name = "avro_asset_multipartition_with_date"
    partitions_def = MultiPartitionsDefinition(
        {
            "date": DailyPartitionsDefinition(start_date="2023-01-01"),
            "spam": StaticPartitionsDefinition(["eggs"]),
        }
    )

    _test_asset_handle_output_path(
        asset_def=build_test_asset_avro(name=asset_name, partitions_def=partitions_def),
        partition_key=MultiPartitionKey({"date": "2023-11-01", "spam": "eggs"}),
        expected_path=f"dagster/staging/test/{asset_name}/_dagster_partition_fiscal_year=2024/_dagster_partition_date=2023-11-01/_dagster_partition_hour=00/_dagster_partition_minute=00/_dagster_partition_spam=eggs/data",
    )


def test_avro_handle_asset_multipartition():
    asset_name = "avro_asset_multipartition"
    partitions_def = MultiPartitionsDefinition(
        {
            "foo": StaticPartitionsDefinition(["bar"]),
            "spam": StaticPartitionsDefinition(["eggs"]),
        }
    )

    _test_asset_handle_output_path(
        asset_def=build_test_asset_avro(name=asset_name, partitions_def=partitions_def),
        partition_key=MultiPartitionKey({"foo": "bar", "spam": "eggs"}),
        expected_path=f"dagster/staging/test/{asset_name}/_dagster_partition_foo=bar/_dagster_partition_spam=eggs/data",
    )


def test_avro_handle_asset_datetime_partition():
    asset_name = "avro_asset_datetime_partition"

    _test_asset_handle_output_path(
        asset_def=build_test_asset_avro(
            name=asset_name,
            partitions_def=DailyPartitionsDefinition(start_date="2023-01-01"),
        ),
        partition_key="2023-11-01",
        expected_path=f"dagster/staging/test/{asset_name}/_dagster_partition_fiscal_year=2024/_dagster_partition_date=2023-11-01/_dagster_partition_hour=00/_dagster_partition_minute=00/data",
    )


def test_avro_handle_asset_static_partition():
    asset_name = "avro_asset_static_partition"

    _test_asset_handle_output_path(
        asset_def=build_test_asset_avro(
            name=asset_name, partitions_def=StaticPartitionsDefinition(["2020"])
        ),
        partition_key="2020",
        expected_path=f"dagster/staging/test/{asset_name}/_dagster_partition_key=2020/data",
    )


def test_file_handle_asset():
    asset_name = "file_asset"

    _test_asset_handle_output_path(
        asset_def=build_test_asset_file(name=asset_name),
        expected_path=f"dagster/staging/test/{asset_name}/data",
    )


def test_file_handle_asset_multipartition_with_date():
    asset_name = "file_asset_multipartition_with_date"
    partitions_def = MultiPartitionsDefinition(
        {
            "date": DailyPartitionsDefinition(start_date="2023-01-01"),
            "spam": StaticPartitionsDefinition(["eggs"]),
        }
    )

    _test_asset_handle_output_path(
        asset_def=build_test_asset_file(name=asset_name, partitions_def=partitions_def),
        partition_key=MultiPartitionKey({"date": "2023-11-01", "spam": "eggs"}),
        expected_path=f"dagster/staging/test/{asset_name}/_dagster_partition_fiscal_year=2024/_dagster_partition_date=2023-11-01/_dagster_partition_hour=00/_dagster_partition_minute=00/_dagster_partition_spam=eggs/data",
    )


def test_file_handle_asset_multipartition():
    asset_name = "file_asset_multipartition"
    partitions_def = MultiPartitionsDefinition(
        {
            "foo": StaticPartitionsDefinition(["bar"]),
            "spam": StaticPartitionsDefinition(["eggs"]),
        }
    )

    _test_asset_handle_output_path(
        asset_def=build_test_asset_file(name=asset_name, partitions_def=partitions_def),
        partition_key=MultiPartitionKey({"foo": "bar", "spam": "eggs"}),
        expected_path=f"dagster/staging/test/{asset_name}/_dagster_partition_foo=bar/_dagster_partition_spam=eggs/data",
    )


def test_file_handle_asset_datetime_partition():
    asset_name = "file_asset_datetime_partition"

    _test_asset_handle_output_path(
        asset_def=build_test_asset_file(
            name=asset_name,
            partitions_def=DailyPartitionsDefinition(start_date="2023-01-01"),
        ),
        partition_key="2023-11-01",
        expected_path=f"dagster/staging/test/{asset_name}/_dagster_partition_fiscal_year=2024/_dagster_partition_date=2023-11-01/_dagster_partition_hour=00/_dagster_partition_minute=00/data",
    )


def test_file_handle_asset_static_partition():
    asset_name = "file_asset_static_partition"

    _test_asset_handle_output_path(
        asset_def=build_test_asset_file(
            name=asset_name, partitions_def=StaticPartitionsDefinition(["2020"])
        ),
        partition_key="2020",
        expected_path=f"dagster/staging/test/{asset_name}/_dagster_partition_key=2020/data",
    )


def test_asset_handle_output_schema():
    class TestSchema(BaseModel):
        foo: str
        spam: str

    asset_def = build_test_asset_avro(
        name="test",
        output_data=[{"foo": "bar", "spam": "eggs"}],
        output_schema=json.loads(py_avro_schema.generate(py_type=TestSchema)),
    )

    result = materialize(assets=[asset_def])

    assert result.success

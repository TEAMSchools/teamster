"""Unit tests for PowerSchool SIS ODBC asset factory."""

from dagster import MonthlyPartitionsDefinition

from teamster.libraries.powerschool.sis.odbc.assets import (
    build_powerschool_table_asset,
)


class TestBuildPowerschoolTableAsset:
    def test_non_partitioned_asset_metadata(self):
        asset_def = build_powerschool_table_asset(
            code_location="loc",
            table_name="STUDENTS",
        )

        asset_key = asset_def.key
        metadata = asset_def.metadata_by_key[asset_key]
        assert metadata["table_name"] == "STUDENTS"
        assert metadata["partition_column"] is None

    def test_partitioned_asset_metadata(self):
        pdef = MonthlyPartitionsDefinition(start_date="2024-01-01")
        asset_def = build_powerschool_table_asset(
            code_location="loc",
            table_name="STOREDGRADES",
            partitions_def=pdef,
            partition_column="WHENMODIFIED",
        )

        asset_key = asset_def.key
        metadata = asset_def.metadata_by_key[asset_key]
        assert metadata["table_name"] == "STOREDGRADES"
        assert metadata["partition_column"] == "WHENMODIFIED"
        assert asset_def.partitions_def is pdef

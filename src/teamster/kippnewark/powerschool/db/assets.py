from dagster import HourlyPartitionsDefinition

from teamster.core.powerschool.db.assets import table_asset_factory

hourly_partition = HourlyPartitionsDefinition(
    start_date="2002-07-01T00:00:00.000000-05:00",
    timezone="US/Eastern",
    fmt="%Y-%m-%dT%H:%M:%S.%f%z",
)

students = table_asset_factory(table_name="students", partitions_def=hourly_partition)
schools = table_asset_factory(table_name="schools", partitions_def=hourly_partition)
gen = table_asset_factory(table_name="gen", partitions_def=hourly_partition)
cc = table_asset_factory(table_name="cc", partitions_def=hourly_partition)

__all__ = [students, schools, gen, cc]

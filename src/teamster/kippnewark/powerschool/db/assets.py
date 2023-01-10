from dagster import TimeWindowPartitionsDefinition

from teamster.core.powerschool.db.assets import table_asset_factory

academic_year_partition = TimeWindowPartitionsDefinition(
    fmt="%Y-%m-%dT%H:%M:%S.%f%z",
    timezone="US/Eastern",
    start="2002-07-01T00:00:00.000000-0400",
    cron_schedule="0 0 1 7 *",
)

students = table_asset_factory(table_name="students")
schools = table_asset_factory(table_name="schools")
gen = table_asset_factory(table_name="gen")
cc = table_asset_factory(
    table_name="cc",
    where={"column": "transaction_date"},
    partitions_def=academic_year_partition,
)

__all__ = [students, schools, gen, cc]

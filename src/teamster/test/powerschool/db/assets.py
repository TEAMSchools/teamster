from dagster import materialize

from teamster.core.powerschool.db.assets import table_asset_factory

PARTITIONS_START_DATE = "2002-07-01T00:00:00.000000-0400"

cc = table_asset_factory(asset_name="cc", partition_start_date=PARTITIONS_START_DATE)


def test_powerschool_table_asset():
    result = materialize(assets=[cc])

    assert result.success

import random

import pendulum
from dagster import AssetsDefinition, DagsterInstance, MultiPartitionKey, materialize

from teamster.code_locations.kipptaf import LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.resources import SSH_RESOURCE_LITTLESIS
from teamster.libraries.core.resources import (
    BIGQUERY_RESOURCE,
    GCS_RESOURCE,
    SSH_COUCHDROP,
)
from teamster.libraries.datagun.assets import format_file_name


def _test_asset(asset: AssetsDefinition, partition_key=None, instance=None):
    if asset.partitions_def is not None and partition_key is None:
        partition_keys = asset.partitions_def.get_partition_keys(
            dynamic_partitions_store=instance
        )

        partition_key = partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))]

    result = materialize(
        assets=[asset],
        partition_key=partition_key,
        instance=instance,
        resources={
            "gcs": GCS_RESOURCE,
            "db_bigquery": BIGQUERY_RESOURCE,
            "ssh_couchdrop": SSH_COUCHDROP,
            "ssh_littlesis": SSH_RESOURCE_LITTLESIS,
        },
    )

    assert result.success


def test_construct_query_schema():
    from teamster.libraries.datagun.assets import construct_query

    group_code = "3LE"
    date = "20230815"

    multi_partition_key = MultiPartitionKey({"group_code": group_code, "date": date})

    query_config = {
        "type": "schema",
        "value": {
            "table": {
                "name": "rpt_gsheets__intacct_integration_file",
                "schema": "kipptaf_extracts",
            }
        },
    }

    query_type = query_config["type"]
    query_value = query_config["value"]

    query_value["where"] = [
        f"{k.dimension_name} = '{k.partition_key}'"
        for k in multi_partition_key.dimension_keys
    ]

    sql = construct_query(query_type=query_type, query_value=query_value)

    print(sql)
    assert str(sql) == (
        "SELECT * \nFROM "
        f"{query_value["table"]["schema"]}.{query_value["table"]["name"]} \n"
        f"WHERE date = '{date}' AND group_code = '{group_code}'"
    )


def test_format_file_name_default():
    from teamster.libraries.datagun.assets import format_file_name

    now = pendulum.now(tz=LOCAL_TIMEZONE)

    today_date_str = now.to_date_string()
    now_timestamp_str = str(now.timestamp()).replace(".", "_")

    file_name = format_file_name(
        stem="foo_{today}_bar_{now}",
        suffix="csv",
        now=now_timestamp_str,
        today=today_date_str,
    )

    print(today_date_str)
    print(now_timestamp_str)
    print(file_name)

    assert file_name == f"foo_{today_date_str}_bar_{now_timestamp_str}.csv"


def test_format_file_name_multi_partition():
    group_code = "3LE"
    date = "20230815"

    multi_partition_key = MultiPartitionKey({"group_code": group_code, "date": date})

    now = pendulum.now(tz=LOCAL_TIMEZONE)

    today_date_str = now.to_date_string()
    now_timestamp_str = str(now.timestamp()).replace(".", "_")

    file_name = format_file_name(
        file_stem="adp_payroll_{date}_{group_code}",
        file_suffix="csv",
        now=now_timestamp_str,
        today=today_date_str,
        **multi_partition_key.keys_by_dimension,
    )

    print(today_date_str)
    print(now_timestamp_str)
    print(file_name)

    assert file_name == f"adp_payroll_{date}_{group_code}.csv"


def test_intacct_extract_asset():
    from teamster.code_locations.kipptaf.datagun.assets import intacct_extract

    _test_asset(
        asset=intacct_extract,
        instance=DagsterInstance.from_config(
            config_dir=".dagster/home", config_filename="dagster-cloud.yaml"
        ),
    )


def test_datagun_powerschool_kippnewark():
    from teamster.code_locations.kippnewark.datagun.assets import (
        powerschool_extract_assets,
    )

    _test_asset(
        asset=powerschool_extract_assets[
            random.randint(a=0, b=(len(powerschool_extract_assets) - 1))
        ]
    )


def test_littlesis_extract():
    from teamster.code_locations.kipptaf.datagun.assets import littlesis_extract

    _test_asset(asset=littlesis_extract)

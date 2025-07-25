import random
from datetime import datetime

from dagster import AssetsDefinition, DagsterInstance, MultiPartitionKey, materialize

from teamster.core.resources import BIGQUERY_RESOURCE, GCS_RESOURCE, SSH_COUCHDROP
from teamster.libraries.extracts.assets import format_file_name


def _test_asset(
    assets: list[AssetsDefinition],
    partition_key=None,
    instance=None,
    asset_selection=None,
    **ssh_kwargs,
):
    if asset_selection is not None:
        asset = [a for a in assets if a.key.to_user_string() == asset_selection][0]
    else:
        asset = assets[random.randint(a=0, b=(len(assets) - 1))]

    if asset.partitions_def is not None and partition_key is None:
        partition_keys = asset.partitions_def.get_partition_keys(
            dynamic_partitions_store=instance
        )

        partition_key = partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))]

    result = materialize(
        assets=[asset],
        partition_key=partition_key,
        instance=instance,
        resources={"gcs": GCS_RESOURCE, "db_bigquery": BIGQUERY_RESOURCE, **ssh_kwargs},
    )

    assert result.success


def test_construct_query_schema():
    from teamster.libraries.extracts.assets import construct_query

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
        f"{query_value['table']['schema']}.{query_value['table']['name']} \n"
        f"WHERE date = '{date}' AND group_code = '{group_code}'"
    )


def test_format_file_name_default():
    from teamster.libraries.extracts.assets import format_file_name

    test_date = datetime(year=1987, month=11, day=5)

    today_date_str = test_date.date().isoformat()
    now_timestamp_str = str(test_date.timestamp()).replace(".", "_")

    file_name = format_file_name(
        stem="foo_{today}_bar_{now}",
        suffix="csv",
        now=now_timestamp_str,
        today=today_date_str,
    )

    print(today_date_str)
    print(now_timestamp_str)
    print(file_name)

    assert file_name == f"foo_1987-11-05_bar_{now_timestamp_str}.csv"


def test_format_file_name_multi_partition():
    from teamster.code_locations.kipptaf import LOCAL_TIMEZONE

    group_code = "3LE"
    date = "20230815"

    multi_partition_key = MultiPartitionKey({"group_code": group_code, "date": date})

    now = datetime.now(LOCAL_TIMEZONE)

    today_date_str = now.date().isoformat()
    now_timestamp_str = str(now.timestamp()).replace(".", "_")

    file_name = format_file_name(
        stem="adp_payroll_{date}_{group_code}",
        suffix="csv",
        now=now_timestamp_str,
        today=today_date_str,
        **multi_partition_key.keys_by_dimension,
    )

    print(today_date_str)
    print(now_timestamp_str)
    print(file_name)

    assert file_name == f"adp_payroll_{date}_{group_code}.csv"


def test_intacct_extract_asset():
    from teamster.code_locations.kipptaf.extracts.assets import intacct_extract

    _test_asset(
        assets=[intacct_extract],
        instance=DagsterInstance.from_config(
            config_dir=".dagster/home", config_filename="dagster-cloud.yaml"
        ),
        ssh_couchdrop=SSH_COUCHDROP,
    )


def test_extracts_powerschool_kippnewark():
    from teamster.code_locations.kippnewark.extracts.assets import (
        powerschool_extract_assets,
    )

    _test_asset(assets=powerschool_extract_assets, ssh_couchdrop=SSH_COUCHDROP)


def test_littlesis_extract():
    from teamster.code_locations.kipptaf.extracts.assets import littlesis_extract
    from teamster.code_locations.kipptaf.resources import SSH_RESOURCE_LITTLESIS

    _test_asset(assets=[littlesis_extract], ssh_littlesis=SSH_RESOURCE_LITTLESIS)


def test_deanslist_jsongz():
    from teamster.code_locations.kipptaf.extracts.assets import (
        deanslist_continuous_extract,
    )
    from teamster.code_locations.kipptaf.resources import SSH_RESOURCE_DEANSLIST

    _test_asset(
        assets=[deanslist_continuous_extract], ssh_deanslist=SSH_RESOURCE_DEANSLIST
    )


def test_clever_extract():
    from teamster.code_locations.kipptaf.extracts.assets import clever_extract_assets
    from teamster.code_locations.kipptaf.resources import SSH_RESOURCE_CLEVER

    _test_asset(
        assets=clever_extract_assets,
        asset_selection="kipptaf/extracts/clever/students_csv",
        ssh_clever=SSH_RESOURCE_CLEVER,
    )


def test_illuminate_extract():
    from teamster.code_locations.kipptaf.extracts.assets import (
        illuminate_extract_assets,
    )
    from teamster.code_locations.kipptaf.resources import SSH_RESOURCE_ILLUMINATE

    _test_asset(
        assets=illuminate_extract_assets, ssh_illuminate=SSH_RESOURCE_ILLUMINATE
    )

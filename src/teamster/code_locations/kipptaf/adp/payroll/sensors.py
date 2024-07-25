import re

import pendulum
from dagster import (
    AddDynamicPartitionsRequest,
    AssetKey,
    DynamicPartitionsDefinition,
    MultiPartitionKey,
    MultiPartitionsDefinition,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    _check,
    define_asset_job,
    sensor,
)

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.adp.payroll.assets import general_ledger_file
from teamster.libraries.ssh.resources import SSHResource


@sensor(
    name=f"{CODE_LOCATION}_adp_payroll_sftp_sensor",
    minimum_interval_seconds=(60 * 10),
    job=define_asset_job(
        name=f"{CODE_LOCATION}_adp_payroll_sftp_asset_job",
        selection=[
            general_ledger_file.key,
            AssetKey(
                [CODE_LOCATION, "adp_payroll", "src_adp_payroll__general_ledger_file"]
            ),
            AssetKey(
                [CODE_LOCATION, "adp_payroll", "stg_adp_payroll__general_ledger_file"]
            ),
            AssetKey(
                [CODE_LOCATION, "extracts", "rpt_gsheets__intacct_integration_file"]
            ),
            AssetKey(
                [
                    CODE_LOCATION,
                    "extracts",
                    "couchdrop",
                    "adp_payroll_date_group_code_csv",
                ]
            ),
        ],
    ),
)
def adp_payroll_sftp_sensor(
    context: SensorEvaluationContext, ssh_couchdrop: SSHResource
):
    now = pendulum.now()
    run_requests = []
    dynamic_partitions_requests = []

    tick_cursor = float(context.cursor or "0.0")

    files = ssh_couchdrop.listdir_attr_r(
        remote_dir=f"/teamster-{CODE_LOCATION}/couchdrop/adp/payroll"
    )

    add_dynamic_partition_keys = set()

    asset_identifier = general_ledger_file.key.to_python_identifier()
    metadata_by_key = general_ledger_file.metadata_by_key[general_ledger_file.key]

    partitions_def = _check.inst(
        obj=general_ledger_file.partitions_def, ttype=MultiPartitionsDefinition
    )

    date_partition = _check.inst(
        obj=partitions_def.get_partitions_def_for_dimension("date"),
        ttype=DynamicPartitionsDefinition,
    )

    context.log.info(asset_identifier)
    pattern = re.compile(
        pattern=(
            rf"{metadata_by_key["remote_dir_regex"]}/"
            rf"{metadata_by_key["remote_file_regex"]}"
        )
    )

    file_matches = [
        (f, path)
        for f, path in files
        if pattern.match(string=path)
        and _check.not_none(value=f.st_mtime) > tick_cursor
        and _check.not_none(value=f.st_size) > 0
    ]

    for f, path in file_matches:
        match = _check.not_none(value=pattern.match(string=path))

        group_dict = match.groupdict()

        partition_key = MultiPartitionKey(group_dict)

        context.log.info(f"{f.filename}: {partition_key}")
        add_dynamic_partition_keys.add(group_dict["date"])
        run_requests.append(
            RunRequest(
                run_key=f"{asset_identifier}__{partition_key}__{now.timestamp()}",
                partition_key=partition_key,
            )
        )

    dynamic_partitions_requests.append(
        AddDynamicPartitionsRequest(
            partitions_def_name=_check.str_param(
                obj=date_partition.name, param_name="partitions_def_name"
            ),
            partition_keys=list(add_dynamic_partition_keys),
        )
    )

    if run_requests:
        tick_cursor = now.timestamp()

    return SensorResult(
        run_requests=run_requests,
        dynamic_partitions_requests=dynamic_partitions_requests,
        cursor=str(tick_cursor),
    )


sensors = [
    adp_payroll_sftp_sensor,
]

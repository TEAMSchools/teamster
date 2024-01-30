import json
import re

import pendulum
from dagster import (
    AddDynamicPartitionsRequest,
    DynamicPartitionsDefinition,
    MultiPartitionKey,
    MultiPartitionsDefinition,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    sensor,
)

from teamster.core.ssh.resources import SSHResource

from ... import CODE_LOCATION, LOCAL_TIMEZONE
from .assets import _all as _all_assets


@sensor(
    name=f"{CODE_LOCATION}_adp_payroll_sftp_sensor",
    minimum_interval_seconds=(60 * 10),
    asset_selection=_all_assets,
)
def adp_payroll_sftp_sensor(
    context: SensorEvaluationContext, ssh_couchdrop: SSHResource
):
    now = pendulum.now(tz=LOCAL_TIMEZONE)

    cursor: dict = json.loads(context.cursor or "{}")

    try:
        files = ssh_couchdrop.listdir_attr_r(
            remote_dir=f"/teamster-{CODE_LOCATION}/couchdrop/adp/payroll", files=[]
        )
    except Exception as e:
        context.log.exception(e)
        return SensorResult(skip_reason=str(e))

    run_requests = []
    dynamic_partitions_requests = []
    for asset in _all_assets:
        add_dynamic_partition_keys = set()

        asset_metadata = asset.metadata_by_key[asset.key]
        asset_identifier = asset.key.to_python_identifier()
        partitions_def: MultiPartitionsDefinition = asset.partitions_def  # type: ignore

        date_partition: DynamicPartitionsDefinition = (
            partitions_def.get_partitions_def_for_dimension("date")
        )  # type: ignore

        context.log.info(asset_identifier)
        last_run = cursor.get(asset_identifier, 0)

        for f in files:
            match = re.match(
                pattern=asset_metadata["remote_file_regex"], string=f.filename
            )

            if match is not None and f.st_mtime > last_run and f.st_size > 0:
                context.log.info(f"{f.filename}: {f.st_mtime} - {f.st_size}")

                group_dict = match.groupdict()

                date_key = group_dict["date"]

                partition_key = MultiPartitionKey(
                    {"date": date_key, "group_code": group_dict["group_code"]}
                )

                add_dynamic_partition_keys.add(date_key)
                run_requests.append(
                    RunRequest(
                        run_key=f"{asset_identifier}__{partition_key}",
                        asset_selection=[asset.key],
                        partition_key=partition_key,
                    )
                )

                cursor[asset_identifier] = now.timestamp()

        dynamic_partitions_requests.append(
            AddDynamicPartitionsRequest(
                partitions_def_name=date_partition.name,  # type: ignore
                partition_keys=list(add_dynamic_partition_keys),
            )
        )

    return SensorResult(
        run_requests=run_requests,
        dynamic_partitions_requests=dynamic_partitions_requests,
        cursor=json.dumps(obj=cursor),
    )


_all = [
    adp_payroll_sftp_sensor,
]

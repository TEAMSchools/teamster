import json
import re

import pendulum
from dagster import (
    AddDynamicPartitionsRequest,
    AssetSelection,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    SkipReason,
    sensor,
)
from paramiko.ssh_exception import SSHException

from teamster.core.ssh.resources import SSHResource

from .. import CODE_LOCATION, LOCAL_TIMEZONE
from . import assets


@sensor(
    name=f"{CODE_LOCATION}_achieve3k_sftp_sensor",
    minimum_interval_seconds=(60 * 10),
    asset_selection=AssetSelection.assets(*assets),
)
def achieve3k_sftp_sensor(context: SensorEvaluationContext, ssh_achieve3k: SSHResource):
    cursor: dict = json.loads(context.cursor or "{}")
    now = pendulum.now(tz=LOCAL_TIMEZONE)

    run_requests = []
    dynamic_partitions_requests = []
    for asset in assets:
        asset_metadata = asset.metadata_by_key[asset.key]
        asset_identifier = asset.key.to_python_identifier()
        context.log.info(asset_identifier)

        last_run = cursor.get(asset_identifier, 0)

        try:
            files = ssh_achieve3k.listdir_attr_r(
                remote_dir=asset_metadata["remote_dir"], files=[]
            )
        except SSHException as e:
            context.log.exception(e)
            return SensorResult(skip_reason=SkipReason(str(e)))
        except ConnectionResetError as e:
            context.log.exception(e)
            return SensorResult(skip_reason=SkipReason(str(e)))

        partition_keys = []
        for f in files:
            match = re.match(
                pattern=asset_metadata["remote_file_regex"], string=f.filename
            )

            if match is not None:
                context.log.info(f"{f.filename}: {f.st_mtime} - {f.st_size}")
                if f.st_mtime > last_run and f.st_size > 0:
                    partition_keys.append(match.group(1))

        if partition_keys:
            for pk in partition_keys:
                run_requests.append(
                    RunRequest(
                        run_key=f"{asset_identifier}_{pk}",
                        asset_selection=[asset.key],
                        partition_key=pk,
                    )
                )

            dynamic_partitions_requests.append(
                AddDynamicPartitionsRequest(
                    partitions_def_name=asset_identifier,
                    partition_keys=partition_keys,
                )
            )

            cursor[asset_identifier] = now.timestamp()

    return SensorResult(
        run_requests=run_requests,
        cursor=json.dumps(obj=cursor),
        dynamic_partitions_requests=dynamic_partitions_requests,
    )


_all = [
    achieve3k_sftp_sensor,
]

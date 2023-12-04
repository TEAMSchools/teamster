import json
import re

import pendulum
from dagster import (
    AssetsDefinition,
    AssetSelection,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    SkipReason,
    sensor,
)
from paramiko.ssh_exception import SSHException

from teamster.core.ssh.resources import SSHResource


def build_sftp_sensor(
    code_location,
    source_system,
    asset_defs: list[AssetsDefinition],
    timezone,
    minimum_interval_seconds=None,
):
    @sensor(
        name=f"{code_location}_{source_system}_sftp_sensor",
        minimum_interval_seconds=minimum_interval_seconds,
        asset_selection=AssetSelection.assets(*asset_defs),
    )
    def _sensor(context: SensorEvaluationContext, ssh_titan: SSHResource):
        now = pendulum.now(tz=timezone)

        cursor: dict = json.loads(context.cursor or "{}")

        run_requests = []
        for asset in asset_defs:
            asset_metadata = asset.metadata_by_key[asset.key]
            asset_identifier = asset.key.to_python_identifier()
            context.log.info(asset_identifier)

            last_run = cursor.get(asset_identifier, 0)

            try:
                files = ssh_titan.listdir_attr_r(
                    remote_dir=asset_metadata["remote_dir"], files=[]
                )
            except SSHException as e:
                context.log.exception(e)
                return SensorResult(skip_reason=SkipReason(str(e)))
            except ConnectionResetError as e:
                context.log.exception(e)
                return SensorResult(skip_reason=SkipReason(str(e)))

            for f in files:
                match = re.match(
                    pattern=asset_metadata["remote_file_regex"], string=f.filename
                )

                if match is not None:
                    context.log.info(f"{f.filename}: {f.st_mtime} - {f.st_size}")
                    if f.st_mtime > last_run and f.st_size > 0:
                        run_requests.append(
                            RunRequest(
                                run_key=f"{asset_identifier}_{f.st_mtime}",
                                asset_selection=[asset.key],
                                partition_key=match.group(1),
                            )
                        )

                cursor[asset_identifier] = now.timestamp()

        return SensorResult(run_requests=run_requests, cursor=json.dumps(obj=cursor))

    return _sensor

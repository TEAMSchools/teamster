import json
import re

import pendulum
from dagster import (
    AssetsDefinition,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    SkipReason,
    sensor,
)
from paramiko.ssh_exception import SSHException

from teamster.core.ssh.resources import SSHResource


def build_sftp_sensor(
    sensor_name,
    asset_defs: list[AssetsDefinition],
    timezone,
    minimum_interval_seconds=None,
):
    @sensor(
        name=sensor_name,
        minimum_interval_seconds=minimum_interval_seconds,
        asset_selection=asset_defs,
    )
    def _sensor(context: SensorEvaluationContext, ssh_edplan: SSHResource):
        now = pendulum.now(tz=timezone)

        cursor: dict = json.loads(context.cursor or "{}")

        run_requests = []
        for asset in asset_defs:
            asset_metadata = asset.metadata_by_key[asset.key]
            asset_identifier = asset.key.to_python_identifier()
            context.log.info(asset_identifier)

            last_run = cursor.get(asset_identifier, 0)

            try:
                files = ssh_edplan.listdir_attr_r(
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
                                partition_key=pendulum.from_timestamp(
                                    timestamp=f.st_mtime
                                ).to_date_string(),
                            )
                        )

                cursor[asset_identifier] = now.timestamp()

        return SensorResult(run_requests=run_requests, cursor=json.dumps(obj=cursor))

    return _sensor

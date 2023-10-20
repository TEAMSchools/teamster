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

from teamster.core.sftp.sensors import get_sftp_ls
from teamster.core.ssh.resources import SSHConfigurableResource


def build_sftp_sensor(
    code_location,
    asset_defs: list[AssetsDefinition],
    timezone,
    minimum_interval_seconds=None,
):
    @sensor(
        name=f"{code_location}_adp_sftp_sensor",
        minimum_interval_seconds=minimum_interval_seconds,
        asset_selection=AssetSelection.assets(*asset_defs),
    )
    def _sensor(
        context: SensorEvaluationContext, ssh_adp_workforce_now: SSHConfigurableResource
    ):
        cursor: dict = json.loads(context.cursor or "{}")
        now = pendulum.now(tz=timezone)

        try:
            ls = get_sftp_ls(ssh=ssh_adp_workforce_now, asset_defs=asset_defs)
        except SSHException as e:
            context.log.error(e)
            return SensorResult(skip_reason=SkipReason(str(e)))
        except ConnectionResetError as e:
            context.log.error(e)
            return SensorResult(skip_reason=SkipReason(str(e)))

        run_requests = []
        for asset_identifier, asset_dict in ls.items():
            context.log.info(asset_identifier)

            last_run = cursor.get(asset_identifier, 0)
            asset = asset_dict["asset"]
            files = asset_dict["files"]

            asset_metadata = asset.metadata_by_key[asset.key]

            updates = []
            for f in files:
                match = re.match(
                    pattern=asset_metadata["remote_file_regex"], string=f.filename
                )

                if match is not None:
                    context.log.info(f"{f.filename}: {f.st_mtime} - {f.st_size}")

                    if f.st_mtime > last_run and f.st_size > 0:
                        updates.append({"mtime": f.st_mtime})

            if updates:
                for u in updates:
                    run_requests.append(
                        RunRequest(
                            run_key=f"{asset_identifier}_{u['mtime']}",
                            asset_selection=[asset.key],
                        )
                    )

            cursor[asset_identifier] = now.timestamp()

        return SensorResult(run_requests=run_requests, cursor=json.dumps(obj=cursor))

    return _sensor

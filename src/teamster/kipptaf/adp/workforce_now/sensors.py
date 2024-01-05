import json
import re

import pendulum
from dagster import RunRequest, SensorEvaluationContext, SensorResult, sensor

from teamster.core.ssh.resources import SSHResource

from ... import CODE_LOCATION, LOCAL_TIMEZONE
from .assets import _all as adp_wfn_sftp_assets


@sensor(
    name=f"{CODE_LOCATION}_adp_sftp_sensor",
    minimum_interval_seconds=(60 * 10),
    asset_selection=adp_wfn_sftp_assets,
)
def adp_wfn_sftp_sensor(
    context: SensorEvaluationContext, ssh_adp_workforce_now: SSHResource
):
    now = pendulum.now(tz=LOCAL_TIMEZONE)

    cursor: dict = json.loads(context.cursor or "{}")

    try:
        files = ssh_adp_workforce_now.listdir_attr_r(remote_dir=".", files=[])
    except Exception as e:
        context.log.exception(e)
        return SensorResult(skip_reason=str(e))

    run_requests = []
    for asset in adp_wfn_sftp_assets:
        asset_metadata = asset.metadata_by_key[asset.key]
        asset_identifier = asset.key.to_python_identifier()

        context.log.info(asset_identifier)
        last_run = cursor.get(asset_identifier, 0)

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


_all = [
    adp_wfn_sftp_sensor,
]

import json
import re

import pendulum
from dagster import RunRequest, SensorEvaluationContext, SensorResult, sensor

from teamster.core.ssh.resources import SSHResource

from .. import CODE_LOCATION, LOCAL_TIMEZONE
from . import assets


@sensor(
    name=f"{CODE_LOCATION}_deanslist_sftp_sensor",
    minimum_interval_seconds=(60 * 10),
    asset_selection=assets,
)
def deanslist_sftp_sensor(context: SensorEvaluationContext, ssh_deanslist: SSHResource):
    now = pendulum.now(tz=LOCAL_TIMEZONE)
    cursor: dict = json.loads(context.cursor or "{}")

    try:
        files = ssh_deanslist.listdir_attr_r(
            remote_dir="reconcile_report_files", files=[]
        )
    except Exception as e:
        context.log.exception(e)
        return SensorResult(skip_reason=str(e))

    asset_selection = []
    for asset in assets:
        asset_metadata = asset.metadata_by_key[asset.key]
        asset_identifier = asset.key.to_string()
        context.log.info(asset_identifier)

        last_run = cursor.get(asset_identifier, 0)

        for f in files:
            match = re.match(
                pattern=asset_metadata["remote_file_regex"], string=f.filename
            )

            if match is not None:
                context.log.info(f"{f.filename}: {f.st_mtime} - {f.st_size}")
                if f.st_mtime > last_run and f.st_size > 0:
                    asset_selection.append(asset.key)

                cursor[asset_identifier] = now.timestamp()

    run_requests = []
    if asset_selection:
        run_requests = [
            RunRequest(
                run_key=f"{context.sensor_name}_{now.timestamp()}",
                asset_selection=asset_selection,
            )
        ]

    return SensorResult(run_requests=run_requests, cursor=json.dumps(obj=cursor))


_all = [
    deanslist_sftp_sensor,
]

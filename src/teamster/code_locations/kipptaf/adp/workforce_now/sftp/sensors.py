import json
import re
from datetime import datetime

from dagster import (
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    _check,
    define_asset_job,
    sensor,
)

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.adp.workforce_now.sftp.assets import assets
from teamster.libraries.ssh.resources import SSHResource

job = define_asset_job(name=f"{CODE_LOCATION}_adp_wfn_sftp_asset_job", selection=assets)


@sensor(name=f"{job.name}_sensor", minimum_interval_seconds=(60 * 10), job=job)
def adp_wfn_sftp_sensor(
    context: SensorEvaluationContext, ssh_adp_workforce_now: SSHResource
):
    now = datetime.now(LOCAL_TIMEZONE)

    run_requests = []
    cursor: dict = json.loads(context.cursor or "{}")

    files = ssh_adp_workforce_now.listdir_attr_r()

    for asset in assets:
        asset_metadata = asset.metadata_by_key[asset.key]
        asset_identifier = asset.key.to_python_identifier()

        context.log.info(asset_identifier)
        last_run = cursor.get(asset_identifier, 0)

        updates = []
        for f, _ in files:
            match = re.match(
                pattern=asset_metadata["remote_file_regex"], string=f.filename
            )

            if (
                match is not None
                and f.st_mtime > last_run
                and _check.not_none(value=f.st_size) > 0
            ):
                context.log.info(f"{f.filename}: {f.st_mtime} - {f.st_size}")
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

    if run_requests:
        return SensorResult(run_requests=run_requests, cursor=json.dumps(obj=cursor))


sensors = [
    adp_wfn_sftp_sensor,
]

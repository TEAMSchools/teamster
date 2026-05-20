import json
import re

from dagster import (
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    SkipReason,
    sensor,
)
from dagster_shared import check

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.adp.workforce_now.sftp.assets import assets
from teamster.libraries.ssh.resources import SSHResource


@sensor(
    name=f"{CODE_LOCATION}__adp__workforce_now__sftp_assets_sensor",
    target=assets,
    minimum_interval_seconds=(60 * 10),
)
def adp_wfn_sftp_sensor(
    context: SensorEvaluationContext, ssh_adp_workforce_now: SSHResource
):
    run_requests = []
    cursor: dict = json.loads(context.cursor or "{}")

    cursor.pop("__dir_mtimes", None)

    min_mtime = min(cursor.values(), default=0)

    with (
        ssh_adp_workforce_now.get_connection() as connection,
        connection.open_sftp() as sftp_client,
    ):
        files = ssh_adp_workforce_now.listdir_attr_r(
            sftp_client=sftp_client,
            exclude_dirs=["./payroll"],
            min_mtime=min_mtime,
        )

    for asset in assets:
        asset_metadata = asset.metadata_by_key[asset.key]
        asset_identifier = asset.key.to_python_identifier()

        context.log.info(asset_identifier)
        last_run = cursor.get(asset_identifier, 0)

        pattern = re.compile(pattern=asset_metadata["remote_file_regex"])

        max_mtime = last_run
        for f, _ in files:
            match = pattern.match(string=f.filename)

            if (
                match is not None
                and f.st_mtime > last_run
                and check.not_none(value=f.st_size) > 0
            ):
                context.log.info(f"{f.filename}: {f.st_mtime} - {f.st_size}")
                run_requests.append(
                    RunRequest(
                        run_key=f"{asset_identifier}_{f.st_mtime}",
                        asset_selection=[asset.key],
                    )
                )

                if check.not_none(value=f.st_mtime) > max_mtime:
                    max_mtime = check.not_none(value=f.st_mtime)

        if max_mtime > last_run:
            cursor[asset_identifier] = max_mtime

    if run_requests:
        return SensorResult(run_requests=run_requests, cursor=json.dumps(obj=cursor))
    else:
        return SkipReason("no new files matching asset patterns")


sensors = [
    adp_wfn_sftp_sensor,
]

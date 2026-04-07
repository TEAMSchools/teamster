import json
import re
from datetime import datetime

from dagster import (
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    SkipReason,
    sensor,
)
from dagster_shared import check

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.adp.workforce_now.sftp.assets import assets
from teamster.libraries.ssh.resources import SSHResource

DIR_MTIMES_KEY = "__dir_mtimes"


@sensor(
    name=f"{CODE_LOCATION}__adp__workforce_now__sftp_assets_sensor",
    target=assets,
    minimum_interval_seconds=(60 * 10),
)
def adp_wfn_sftp_sensor(
    context: SensorEvaluationContext, ssh_adp_workforce_now: SSHResource
):
    now = datetime.now(LOCAL_TIMEZONE)

    run_requests = []
    cursor: dict = json.loads(context.cursor or "{}")

    dir_mtimes = cursor.pop(DIR_MTIMES_KEY, {})

    asset_cursors = {k: v for k, v in cursor.items() if k != DIR_MTIMES_KEY}
    min_mtime = min(asset_cursors.values(), default=0)

    result = ssh_adp_workforce_now.listdir_attr_r(
        exclude_dirs=["./payroll"],
        min_mtime=min_mtime,
        dir_mtimes=dir_mtimes,
    )

    # dir_mtimes is always passed, so result is always a tuple
    assert isinstance(result, tuple)
    files, dir_mtimes = result

    for asset in assets:
        asset_metadata = asset.metadata_by_key[asset.key]
        asset_identifier = asset.key.to_python_identifier()

        context.log.info(asset_identifier)
        last_run = cursor.get(asset_identifier, 0)

        pattern = re.compile(pattern=asset_metadata["remote_file_regex"])

        updates = []
        for f, _ in files:
            match = pattern.match(string=f.filename)

            if (
                match is not None
                and f.st_mtime > last_run
                and check.not_none(value=f.st_size) > 0
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

    cursor[DIR_MTIMES_KEY] = dir_mtimes

    if run_requests:
        return SensorResult(run_requests=run_requests, cursor=json.dumps(obj=cursor))
    else:
        return SkipReason()


sensors = [
    adp_wfn_sftp_sensor,
]

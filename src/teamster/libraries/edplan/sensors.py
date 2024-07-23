import json
import re
from socket import gaierror

import pendulum
from dagster import (
    AssetsDefinition,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    SkipReason,
    _check,
    define_asset_job,
    sensor,
)

from teamster.libraries.ssh.resources import SSHResource


def build_edplan_sftp_sensor(
    code_location: str,
    asset: AssetsDefinition,
    timezone,
    minimum_interval_seconds=None,
):
    job = define_asset_job(
        name=f"{code_location}_edplan_sftp_asset_job", selection=[asset]
    )

    @sensor(
        name=f"{job.name}_sensor",
        job=job,
        minimum_interval_seconds=minimum_interval_seconds,
    )
    def _sensor(context: SensorEvaluationContext, ssh_edplan: SSHResource):
        now_timestamp = pendulum.now(tz=timezone).timestamp()

        run_requests = []
        cursor: dict = json.loads(context.cursor or "{}")

        try:
            files = ssh_edplan.listdir_attr_r("Reports")
        except gaierror as e:
            if "[Errno -3] Temporary failure in name resolution" in e.args:
                context.log.error(msg=str(e))
                return SkipReason(str(e))
            else:
                raise e

        asset_identifier = asset.key.to_python_identifier()
        context.log.info(asset_identifier)

        last_run = cursor.get(asset_identifier, 0)

        for f, _ in files:
            match = re.match(
                pattern=asset.metadata_by_key[asset.key]["remote_file_regex"],
                string=f.filename,
            )

            if (
                match is not None
                and f.st_mtime > last_run
                and _check.not_none(value=f.st_size) > 0
            ):
                context.log.info(f"{f.filename}: {f.st_mtime} - {f.st_size}")
                partition_key = pendulum.from_timestamp(
                    timestamp=_check.not_none(value=f.st_mtime)
                ).to_date_string()

                run_requests.append(
                    RunRequest(
                        run_key=f"{asset_identifier}_{partition_key}_{now_timestamp}",
                        partition_key=partition_key,
                    )
                )

            cursor[asset_identifier] = now_timestamp

        return SensorResult(run_requests=run_requests, cursor=json.dumps(obj=cursor))

    return _sensor

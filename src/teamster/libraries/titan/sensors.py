import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from dagster import (
    AssetsDefinition,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    SkipReason,
    sensor,
)
from dagster_shared import check
from paramiko.ssh_exception import SSHException

from teamster.libraries.ssh.resources import SSHResource


def build_titan_sftp_sensor(
    code_location: str,
    timezone: ZoneInfo,
    asset_selection: list[AssetsDefinition],
    minimum_interval_seconds: int | None = None,
    exclude_dirs: list | None = None,
):
    if exclude_dirs is None:
        exclude_dirs = []

    @sensor(
        name=f"{code_location}__titan__sftp_asset_sensor",
        target=asset_selection,
        minimum_interval_seconds=minimum_interval_seconds,
    )
    def _sensor(context: SensorEvaluationContext, ssh_titan: SSHResource):
        now_timestamp = datetime.now(timezone).timestamp()

        run_requests = []
        cursor: dict = json.loads(context.cursor or "{}")

        try:
            files = ssh_titan.listdir_attr_r(exclude_dirs=exclude_dirs)
        except SSHException as e:
            return SkipReason(str(e))

        for a in asset_selection:
            asset_identifier = a.key.to_python_identifier()
            context.log.info(asset_identifier)

            last_run = cursor.get(asset_identifier, 0)

            for f, _ in files:
                match = re.match(
                    pattern=a.metadata_by_key[a.key]["remote_file_regex"],
                    string=f.filename,
                )

                if (
                    match is not None
                    and f.st_mtime > last_run
                    and check.not_none(value=f.st_size) > 0
                ):
                    context.log.info(f"{f.filename}: {f.st_mtime} - {f.st_size}")
                    partition_key = match.group(1)

                    run_requests.append(
                        RunRequest(
                            run_key=(
                                f"{a.key.to_python_identifier()}_{partition_key}_"
                                f"{now_timestamp}"
                            ),
                            asset_selection=[a.key],
                            partition_key=partition_key,
                        )
                    )

                    cursor[asset_identifier] = now_timestamp

        return SensorResult(run_requests=run_requests, cursor=json.dumps(obj=cursor))

    return _sensor

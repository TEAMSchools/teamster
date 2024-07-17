import json
import re

import pendulum
from dagster import (
    AssetsDefinition,
    MultiPartitionKey,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    _check,
    sensor,
)

from teamster.libraries.ssh.resources import SSHResource


def build_iready_sftp_sensor(
    code_location: str,
    asset_defs: list[AssetsDefinition],
    timezone,
    remote_dir_regex: str,
    current_fiscal_year: int,
    minimum_interval_seconds=None,
):
    @sensor(
        name=f"{code_location}_iready_sftp_sensor",
        minimum_interval_seconds=minimum_interval_seconds,
        asset_selection=asset_defs,
    )
    def _sensor(context: SensorEvaluationContext, ssh_iready: SSHResource):
        now = pendulum.now(tz=timezone)

        cursor: dict = json.loads(context.cursor or "{}")

        run_requests = []

        files = ssh_iready.listdir_attr_r(remote_dir=remote_dir_regex)

        for asset in asset_defs:
            metadata_by_key = asset.metadata_by_key[asset.key]
            asset_identifier = asset.key.to_python_identifier()

            context.log.info(asset_identifier)
            last_run = cursor.get(asset_identifier, 0)

            pattern = re.compile(
                pattern=(
                    f"{metadata_by_key["remote_dir_regex"]}/"
                    f"{metadata_by_key["remote_file_regex"]}"
                )
            )

            file_matches = [
                (f, path)
                for f, path in files
                if pattern.match(string=path)
                and _check.not_none(value=f.st_mtime) > last_run
                and _check.not_none(value=f.st_size) > 0
            ]

            for f, path in file_matches:
                match = _check.not_none(value=pattern.match(string=path))

                group_dict = match.groupdict()

                if group_dict["academic_year"] == "Current_Year":
                    partition_key = MultiPartitionKey(
                        {
                            "academic_year": str(current_fiscal_year - 1),
                            "subject": group_dict["subject"],
                        }
                    )
                else:
                    partition_key = MultiPartitionKey(group_dict)

                context.log.info(f"{f.filename}: {partition_key}")
                run_requests.append(
                    RunRequest(
                        run_key=(
                            f"{asset_identifier}__{partition_key}__{now.timestamp()}"
                        ),
                        asset_selection=[asset.key],
                        partition_key=partition_key,
                    )
                )

                cursor[asset_identifier] = now.timestamp()

        return SensorResult(run_requests=run_requests, cursor=json.dumps(obj=cursor))

    return _sensor

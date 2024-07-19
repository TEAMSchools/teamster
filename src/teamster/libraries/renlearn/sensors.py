import json
import re

import pendulum
from dagster import (
    AssetsDefinition,
    MultiPartitionKey,
    MultiPartitionsDefinition,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    _check,
    define_asset_job,
    sensor,
)

from teamster.libraries.ssh.resources import SSHResource


def build_renlearn_sftp_sensor(
    code_location: str,
    asset_selection: list[AssetsDefinition],
    partition_key_start_date: str,
    timezone,
    minimum_interval_seconds=None,
    tags=None,
):
    job = define_asset_job(
        name=f"{code_location}_renlearn_sftp_asset_job", selection=asset_selection
    )

    @sensor(
        name=f"{job.name}_sensor",
        job=job,
        minimum_interval_seconds=minimum_interval_seconds,
    )
    def _sensor(context: SensorEvaluationContext, ssh_renlearn: SSHResource):
        now_timestamp = pendulum.now(tz=timezone).timestamp()
        cursor: dict = json.loads(context.cursor or "{}")

        files = ssh_renlearn.listdir_attr_r()

        run_requests = []
        for asset in asset_selection:
            asset_metadata = asset.metadata_by_key[asset.key]
            asset_identifier = asset.key.to_python_identifier()
            context.log.info(asset_identifier)

            last_run = cursor.get(asset_identifier, 0)

            partitions_def = _check.inst(
                asset.partitions_def, MultiPartitionsDefinition
            )

            subjects = partitions_def.get_partitions_def_for_dimension("subject")

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
                    for subject in subjects.get_partition_keys():
                        run_requests.append(
                            RunRequest(
                                run_key=f"{asset_identifier}_{now_timestamp}",
                                asset_selection=[asset.key],
                                tags=tags,
                                partition_key=MultiPartitionKey(
                                    {
                                        "start_date": partition_key_start_date,
                                        "subject": subject,
                                    }
                                ),
                            )
                        )

                cursor[asset_identifier] = now_timestamp

        return SensorResult(run_requests=run_requests, cursor=json.dumps(obj=cursor))

    return _sensor

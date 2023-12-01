import json
import re

import pendulum
from dagster import (
    AssetsDefinition,
    AssetSelection,
    MultiPartitionKey,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    SkipReason,
    StaticPartitionsDefinition,
    sensor,
)
from paramiko.ssh_exception import SSHException

from teamster.core.sftp.assets import listdir_attr_r
from teamster.core.ssh.resources import SSHResource


def build_sftp_sensor(
    code_location,
    source_system,
    asset_defs: list[AssetsDefinition],
    fiscal_year,
    timezone,
    minimum_interval_seconds=None,
):
    fiscal_year_start_string = fiscal_year.start.to_date_string()

    @sensor(
        name=f"{code_location}_{source_system}_sftp_sensor",
        minimum_interval_seconds=minimum_interval_seconds,
        asset_selection=AssetSelection.assets(*asset_defs),
    )
    def _sensor(context: SensorEvaluationContext, ssh_renlearn: SSHResource):
        cursor: dict = json.loads(context.cursor or "{}")
        now = pendulum.now(tz=timezone)

        run_requests = []
        for asset in asset_defs:
            asset_metadata = asset.metadata_by_key[asset.key]
            asset_identifier = asset.key.to_python_identifier()
            context.log.info(asset_identifier)

            last_run = cursor.get(asset_identifier, 0)

            try:
                with ssh_renlearn.get_connection() as conn:
                    with conn.open_sftp() as sftp_client:
                        files = listdir_attr_r(
                            sftp_client=sftp_client,
                            remote_dir=asset_metadata["remote_dir"],
                            files=[],
                        )
            except SSHException as e:
                context.log.exception(e)
                return SensorResult(skip_reason=SkipReason(str(e)))
            except ConnectionResetError as e:
                context.log.exception(e)
                return SensorResult(skip_reason=SkipReason(str(e)))

            subjects: StaticPartitionsDefinition = (
                asset.partitions_def.get_partitions_def_for_dimension("subject")
            )

            for f in files:
                match = re.match(
                    pattern=asset_metadata["remote_file_regex"], string=f.filename
                )

                if match is not None:
                    context.log.info(f"{f.filename}: {f.st_mtime} - {f.st_size}")
                    if f.st_mtime > last_run and f.st_size > 0:
                        for subject in subjects.get_partition_keys():
                            run_requests.append(
                                RunRequest(
                                    run_key=f"{asset_identifier}_{f.st_mtime}",
                                    asset_selection=[asset.key],
                                    partition_key=MultiPartitionKey(
                                        {
                                            "start_date": fiscal_year_start_string,
                                            "subject": subject,
                                        }
                                    ),
                                )
                            )

                cursor[asset_identifier] = now.timestamp()

        return SensorResult(run_requests=run_requests, cursor=json.dumps(obj=cursor))

    return _sensor

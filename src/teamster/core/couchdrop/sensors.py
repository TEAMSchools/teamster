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
    StaticPartitionsDefinition,
    sensor,
)

from teamster.core.ssh.resources import SSHResource


def build_couchdrop_sftp_sensor(
    code_location, local_timezone, assets: list[AssetsDefinition]
):
    @sensor(
        name=f"{code_location}_couchdrop_sftp_sensor",
        minimum_interval_seconds=(60 * 10),
        asset_selection=assets,
    )
    def _sensor(context: SensorEvaluationContext, ssh_couchdrop: SSHResource):
        run_requests = []
        now = pendulum.now(tz=local_timezone)
        cursor: dict = json.loads(context.cursor or "{}")

        try:
            files = ssh_couchdrop.listdir_attr_r(
                remote_dir=f"/data-team/{code_location}", files=[]
            )
        except Exception as e:
            context.log.exception(e)
            return SensorResult(skip_reason=str(e))

        for asset in assets:
            asset_identifier = asset.key.to_python_identifier()
            metadata_by_key = asset.metadata_by_key[asset.key]

            context.log.info(asset_identifier)
            pattern = re.compile(
                pattern=f"{metadata_by_key["remote_dir"]}/{metadata_by_key["remote_file_regex"]}"
            )

            file_matches = [
                f
                for f in files
                if pattern.match(string=f.filepath)
                and f.st_mtime > cursor.get(asset_identifier, 0)
                and f.st_size > 0
            ]

            for f in file_matches:
                cursor[asset_identifier] = now.timestamp()

                match = pattern.match(string=f.filepath)

                if isinstance(asset.partitions_def, MultiPartitionsDefinition):
                    partition_key = MultiPartitionKey(match.groupdict())
                elif isinstance(asset.partitions_def, StaticPartitionsDefinition):
                    partition_key = match.group(1)
                else:
                    partition_key = None

                context.log.info(f"{f.filename}: {partition_key}")
                run_requests.append(
                    RunRequest(
                        run_key=f"{context.sensor_name}_{now.timestamp()}",
                        asset_selection=[asset.key],
                        partition_key=partition_key,
                    )
                )

        return SensorResult(run_requests=run_requests, cursor=json.dumps(obj=cursor))

    return _sensor

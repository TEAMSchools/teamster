import json
import re

import pendulum
from dagster import (  # MultiPartitionKey,; RunRequest,
    AddDynamicPartitionsRequest,
    AssetsDefinition,
    AssetSelection,
    SensorEvaluationContext,
    SensorResult,
    sensor,
)
from dagster_ssh import SSHResource


def build_sftp_sensor(
    code_location,
    source_system,
    asset_defs: list[AssetsDefinition],
    minimum_interval_seconds=None,
):
    @sensor(
        name=f"{code_location}_{source_system}_sftp_sensor",
        minimum_interval_seconds=minimum_interval_seconds,
        asset_selection=AssetSelection.assets(*asset_defs),
        required_resource_keys={f"sftp_{source_system}"},
    )
    def _sensor(context: SensorEvaluationContext):
        now = pendulum.now()
        cursor: dict = json.loads(context.cursor or "{}")

        sftp: SSHResource = context.resources[f"sftp_{source_system}"]

        ls = {}
        conn = sftp.get_connection()
        with conn.open_sftp() as sftp_client:
            for asset in asset_defs:
                ls[asset.key.to_python_identifier()] = {
                    "files": sftp_client.listdir_attr(
                        path=asset.metadata_by_key[asset.key]["remote_filepath"]
                    ),
                    "asset": asset,
                }
        conn.close()

        # run_requests = []
        dynamic_partitions_requests = []
        for asset_identifier, asset_dict in ls.items():
            asset = asset_dict["asset"]
            files = asset_dict["files"]

            last_run = cursor.get(asset_identifier, 0)

            partition_keys = []
            for f in files:
                context.log.info(f"{f.filename}: {f.st_mtime} - {f.st_size}")

                match = re.match(
                    pattern=asset.metadata_by_key[asset.key]["remote_file_regex"],
                    string=f.filename,
                )

                if match is not None and f.st_mtime >= last_run and f.st_size > 0:
                    partition_keys.append(match.groupdict())

            if partition_keys:
                # for pk in partition_keys:
                #     run_requests.append(
                #         RunRequest(
                #             run_key=f"{asset_identifier}_{pk}",
                #             asset_selection=[asset.key],
                #             partition_key=MultiPartitionKey(pk),
                #         )
                #     )

                dynamic_partitions_requests.append(
                    AddDynamicPartitionsRequest(
                        partitions_def_name=f"{asset_identifier}_date",
                        partition_keys=list(set([pk["date"] for pk in partition_keys])),
                    )
                )

                cursor[asset_identifier] = now.timestamp()

        return SensorResult(
            # run_requests=run_requests,
            cursor=json.dumps(obj=cursor),
            dynamic_partitions_requests=dynamic_partitions_requests,
        )

    return _sensor

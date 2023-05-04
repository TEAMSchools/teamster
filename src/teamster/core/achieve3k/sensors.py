import json
import re

import pendulum
from dagster import (
    AddDynamicPartitionsRequest,
    AssetsDefinition,
    AssetSelection,
    ResourceParam,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    sensor,
)
from dagster_ssh import SSHResource


def build_sftp_sensor(
    code_location, asset_defs: list[AssetsDefinition], minimum_interval_seconds=None
):
    @sensor(
        name=f"{code_location}_achieve3k_sftp_sensor",
        minimum_interval_seconds=minimum_interval_seconds,
        asset_selection=AssetSelection.assets(*asset_defs),
    )
    def _sensor(
        context: SensorEvaluationContext,
        sftp_clever_reports: ResourceParam[SSHResource],
    ):
        now = pendulum.now()
        cursor: dict = json.loads(context.cursor or "{}")
        context.instance.get_asset_keys

        conn = sftp_clever_reports.get_connection()

        with conn.open_sftp() as sftp_client:
            ls = {}
            for asset in asset_defs:
                ls[asset.key.path[-1]] = sftp_client.listdir_attr(
                    path=asset.metadata_by_key[asset.key]["remote_filepath"]
                )

        conn.close()

        run_requests = []
        dynamic_partitions_requests = []

        for asset_name, files in ls.items():
            last_run = cursor.get(asset_name, 0)
            asset = [a for a in asset_defs if a.key.path[-1] == asset_name][0]

            partition_keys = []
            for f in files:
                context.log.info(f"{f.filename}: {f.st_mtime} - {f.st_size}")

                match = re.match(
                    pattern=asset.metadata_by_key[asset.key]["remote_file_regex"],
                    string=f.filename,
                )

                if match and f.st_mtime >= last_run and f.st_size > 0:
                    partition_keys.append(match.group(1))

            if partition_keys:
                for pk in partition_keys:
                    run_requests.append(
                        RunRequest(
                            run_key=f"{asset.key.to_python_identifier()}_{pk}",
                            asset_selection=[asset.key],
                            partition_key=pk,
                        )
                    )

                dynamic_partitions_requests.append(
                    AddDynamicPartitionsRequest(
                        partitions_def_name=(f"{code_location}_achieve3k_{asset_name}"),
                        partition_keys=partition_keys,
                    )
                )

                cursor[asset_name] = now.timestamp()

        return SensorResult(
            run_requests=run_requests,
            cursor=json.dumps(obj=cursor),
            dynamic_partitions_requests=dynamic_partitions_requests,
        )

    return _sensor

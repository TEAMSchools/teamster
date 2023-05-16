import json
import re

from dagster import (
    AssetsDefinition,
    AssetSelection,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    sensor,
)
from dagster_ssh import SSHResource

from teamster.core.utils.variables import NOW


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
        cursor: dict = json.loads(context.cursor or "{}")

        ssh: SSHResource = getattr(context.resources, f"sftp_{source_system}")

        ls = {}
        conn = ssh.get_connection()
        with conn.open_sftp() as sftp_client:
            for asset in asset_defs:
                ls[asset.key.to_python_identifier()] = {
                    "asset": asset,
                    "files": sftp_client.listdir_attr(
                        path=asset.metadata_by_key[asset.key]["remote_filepath"]
                    ),
                }
        conn.close()

        run_requests = []
        for asset_identifier, asset_dict in ls.items():
            context.log.info(asset_identifier)

            asset = asset_dict["asset"]
            files = asset_dict["files"]

            last_run = cursor.get(asset_identifier, 0)

            for f in files:
                match = re.match(
                    pattern=asset.metadata_by_key[asset.key]["remote_file_regex"],
                    string=f.filename,
                )

                if match is not None:
                    context.log.info(f"{f.filename}: {f.st_mtime} - {f.st_size}")
                    if f.st_mtime > last_run and f.st_size > 0:
                        run_requests.append(
                            RunRequest(
                                run_key=f"{asset_identifier}_{f.st_mtime}",
                                asset_selection=[asset.key],
                                partition_key=match.group(1),
                            )
                        )

                cursor[asset_identifier] = NOW.timestamp()

        return SensorResult(run_requests=run_requests, cursor=json.dumps(obj=cursor))

    return _sensor

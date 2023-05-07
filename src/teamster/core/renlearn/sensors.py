import json
import re

import pendulum
from dagster import (
    AssetSelection,
    ResourceParam,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    sensor,
)
from dagster_ssh import SSHResource


def build_sftp_sensor(code_location, asset_defs, minimum_interval_seconds=None):
    @sensor(
        name=f"{code_location}_renlearn_sftp_sensor",
        minimum_interval_seconds=minimum_interval_seconds,
        asset_selection=AssetSelection.assets(*asset_defs),
    )
    def _sensor(
        context: SensorEvaluationContext, sftp_renlearn: ResourceParam[SSHResource]
    ):
        now = pendulum.now()
        cursor: dict = json.loads(context.cursor or "{}")

        ls = {}
        conn = sftp_renlearn.get_connection()
        with conn.open_sftp() as sftp_client:
            for asset in asset_defs:
                ls[asset.key.to_python_identifier()] = {
                    "files": sftp_client.listdir_attr(
                        path=asset.metadata_by_key[asset.key]["remote_filepath"]
                    ),
                    "asset": asset,
                }
        conn.close()

        run_requests = []
        for asset_identifier, asset_dict in ls.items():
            asset = asset_dict["asset"]
            files = asset_dict["files"]

            last_run = cursor.get(asset_identifier, 0)

            for f in files:
                context.log.info(f"{f.filename}: {f.st_mtime} - {f.st_size}")

                match = re.match(
                    pattern=asset.metadata_by_key[asset.key], string=f.filename
                )

                if match is not None and f.st_mtime >= last_run and f.st_size > 0:
                    run_requests.append(
                        RunRequest(
                            run_key=f"{asset_identifier}_{now.timestamp()}",
                            asset_selection=[asset.key],
                        )
                    )

                cursor[asset_identifier] = now.timestamp()

        return SensorResult(run_requests=run_requests, cursor=json.dumps(obj=cursor))

    return _sensor

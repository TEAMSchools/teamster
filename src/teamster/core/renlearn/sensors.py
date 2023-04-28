import json

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

        conn = sftp_renlearn.get_connection()

        with conn.open_sftp() as sftp_client:
            ls = sftp_client.listdir_attr()

        conn.close()

        asset_selection = []
        for f in ls:
            last_run = cursor.get(f.filename, 0)
            asset_match = [
                a
                for a in asset_defs
                if a.metadata_by_key[a.key]["remote_filepath"] == f.filename
            ]

            if asset_match:
                context.log.info(f"{f.filename}: {f.st_mtime} - {f.st_size}")

                if f.st_mtime >= last_run and f.st_size > 0:
                    for asset in asset_match:
                        asset_selection.append(asset.key)

                    cursor[f.filename] = now.timestamp()

        return SensorResult(
            run_requests=RunRequest(
                run_key=f"{code_location}_renlearn_sftp_{f.st_mtime}",
                asset_selection=asset_selection,
            ),
            cursor=json.dumps(obj=cursor),
        )

    return _sensor

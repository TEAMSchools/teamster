import json

import pendulum
from dagster import (
    AssetKey,
    ResourceParam,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    sensor,
)
from dagster_ssh import SSHResource


def build_sftp_sensor(
    code_location, asset_configs: list[dict], minimum_interval_seconds=None
):
    @sensor(
        name=f"{code_location}_renlearn_sftp_sensor",
        minimum_interval_seconds=minimum_interval_seconds,
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

        run_requests = []
        for f in ls:
            last_run = cursor.get(f.filename, 0)
            asset_match = [
                a for a in asset_configs if a["remote_filepath"] == f.filename
            ]

            if asset_match:
                context.log.info(f"{f.filename}: {f.st_mtime}")

                if f.st_mtime >= last_run:
                    asset_key = AssetKey(
                        [code_location, "renlearn", asset_match[0]["asset_name"]]
                    )

                    run_requests.append(
                        RunRequest(
                            run_key=asset_key.to_python_identifier(),
                            asset_selection=[asset_key],
                        )
                    )
                    cursor[f.filename] = now.timestamp()

        return SensorResult(run_requests=run_requests, cursor=cursor)

    return _sensor

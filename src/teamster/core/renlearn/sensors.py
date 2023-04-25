import json

import pendulum
from dagster import (
    ResourceParam,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    define_asset_job,
    sensor,
)
from dagster_ssh import SSHResource


def build_sftp_sensor(code_location, asset_selection, minimum_interval_seconds=None):
    asset_job = define_asset_job(
        name=f"{code_location}__renlearn__asset_job", selection=asset_selection
    )

    @sensor(
        name=f"{code_location}_renlearn_sftp_sensor",
        job=asset_job,
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

        run_asset_selection = []
        for f in ls:
            last_run = cursor.get(f.filename, 0)
            asset_match = [
                a
                for a in asset_selection
                if a.metadata_by_key[a.key]["remote_filepath"] == f.filename
            ]

            if asset_match:
                context.log.info(f"{f.filename}: {f.st_mtime}")

                if f.st_mtime >= last_run:
                    context.log.info(asset_match[0].key)
                    run_asset_selection.append(asset_match[0].key)
                    cursor[f.filename] = now.timestamp()

        return SensorResult(
            run_requests=[
                RunRequest(run_key=asset_job.name, asset_selection=run_asset_selection)
            ],
            cursor=json.dumps(obj=cursor),
        )

    return _sensor

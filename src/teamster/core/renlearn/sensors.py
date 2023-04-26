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


def build_sftp_sensor(code_location, asset_defs, minimum_interval_seconds=None):
    asset_jobs = [
        define_asset_job(
            name=f"{asset.key.to_python_identifier()}_job",
            selection=[asset],
            partitions_def=asset.partitions_def,
        )
        for asset in asset_defs
    ]

    @sensor(
        name=f"{code_location}_renlearn_sftp_sensor",
        jobs=asset_jobs,
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
                a
                for a in asset_defs
                if a.metadata_by_key[a.key]["remote_filepath"] == f.filename
            ]

            if asset_match:
                context.log.info(f"{f.filename}: {f.st_mtime} - {f.st_size}")

                if f.st_mtime >= last_run and f.st_size > 0:
                    asset = asset_match[0]

                    run_requests.append(
                        RunRequest(
                            run_key=f"{asset.key.to_python_identifier()}_job",
                            asset_selection=[asset.key],
                        )
                    )
                    cursor[f.filename] = now.timestamp()

        return SensorResult(run_requests=run_requests, cursor=json.dumps(obj=cursor))

    return _sensor

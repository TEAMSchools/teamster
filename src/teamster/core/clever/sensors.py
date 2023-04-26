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
        name=f"{code_location}_clever_sftp_sensor",
        jobs=asset_jobs,
        minimum_interval_seconds=minimum_interval_seconds,
    )
    def _sensor(
        context: SensorEvaluationContext, sftp_clever: ResourceParam[SSHResource]
    ):
        now = pendulum.now()
        cursor: dict = json.loads(context.cursor or "{}")

        conn = sftp_clever.get_connection()

        with conn.open_sftp() as sftp_client:
            ls = {}
            for asset in asset_defs:
                remote_filepath = asset.metadata_by_key[asset.key]["remote_filepath"]

                ls[remote_filepath] = sftp_client.listdir_attr(path=remote_filepath)

        conn.close()

        run_requests = []
        for remote_filepath, files in ls.items():
            asset = [a for a in asset_defs if a.name == remote_filepath][0]
            last_run = cursor.get(remote_filepath, 0)

            asset_job_name = f"{asset.key.to_python_identifier()}_job"

            partition_keys = set()
            for f in files:
                context.log.info(f"{f.filename}: {f.st_mtime} - {f.st_size}")
                if f.st_mtime >= last_run and f.st_size > 0:
                    partition_keys.add(f.filename)

            if partition_keys:
                for pk in partition_keys:
                    run_requests.append(
                        RunRequest(
                            run_key=asset_job_name,
                            job_name=[
                                j for j in asset_jobs if j.name == asset_job_name
                            ][0].name,
                            asset_selection=[asset.key],
                            partition_key=pk,
                        )
                    )
                cursor[remote_filepath] = now.timestamp()

        return SensorResult(run_requests=run_requests, cursor=json.dumps(obj=cursor))

    return _sensor

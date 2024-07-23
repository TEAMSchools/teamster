import json
import re
from collections import defaultdict
from itertools import groupby
from operator import itemgetter

import pendulum
from dagster import (
    AssetKey,
    AssetsDefinition,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    SkipReason,
    _check,
    define_asset_job,
    sensor,
)
from paramiko.ssh_exception import SSHException

from teamster.libraries.ssh.resources import SSHResource


def build_titan_sftp_sensor(
    code_location: str,
    asset_selection: list[AssetsDefinition],
    timezone,
    minimum_interval_seconds: int | None = None,
    exclude_dirs: list | None = None,
):
    base_job_name = f"{code_location}_titan_sftp_asset_job"

    if exclude_dirs is None:
        exclude_dirs = []

    keys_by_partitions_def = defaultdict(set[AssetKey])

    for assets_def in asset_selection:
        keys_by_partitions_def[assets_def.partitions_def].add(assets_def.key)

    jobs = [
        define_asset_job(
            name=(
                f"{base_job_name}_{partitions_def.get_serializable_unique_identifier()}"
            ),
            selection=list(keys),
        )
        for partitions_def, keys in keys_by_partitions_def.items()
    ]

    @sensor(
        name=f"{base_job_name}_sensor",
        jobs=jobs,
        minimum_interval_seconds=minimum_interval_seconds,
    )
    def _sensor(context: SensorEvaluationContext, ssh_titan: SSHResource):
        now_timestamp = pendulum.now(tz=timezone).timestamp()

        run_request_kwargs = []
        run_requests = []
        cursor: dict = json.loads(context.cursor or "{}")

        try:
            files = ssh_titan.listdir_attr_r(exclude_dirs=exclude_dirs)
        except SSHException as e:
            context.log.error(msg=e)
            if "No existing session" in e.args:
                return SkipReason(str(e))
            else:
                raise SSHException from e
        except TimeoutError as e:
            if "timed out" in e.args:
                return SkipReason(str(e))
            else:
                raise TimeoutError from e

        for a in asset_selection:
            asset_identifier = a.key.to_python_identifier()
            partitions_def = _check.not_none(value=a.partitions_def)
            context.log.info(asset_identifier)

            last_run = cursor.get(asset_identifier, 0)

            for f, _ in files:
                match = re.match(
                    pattern=a.metadata_by_key[a.key]["remote_file_regex"],
                    string=f.filename,
                )

                if (
                    match is not None
                    and f.st_mtime > last_run
                    and _check.not_none(value=f.st_size) > 0
                ):
                    context.log.info(f"{f.filename}: {f.st_mtime} - {f.st_size}")
                    run_request_kwargs.append(
                        {
                            "asset_key": a.key,
                            "job_name": (
                                f"{base_job_name}_"
                                f"{partitions_def.get_serializable_unique_identifier()}"
                            ),
                            "partition_key": match.group(1),
                        }
                    )

                cursor[asset_identifier] = now_timestamp

        for (job_name, parition_key), group in groupby(
            iterable=run_request_kwargs, key=itemgetter("job_name", "partition_key")
        ):
            run_requests.append(
                RunRequest(
                    run_key=f"{job_name}_{parition_key}_{now_timestamp}",
                    job_name=job_name,
                    partition_key=parition_key,
                    asset_selection=[g["asset_key"] for g in group],
                )
            )

        return SensorResult(run_requests=run_requests, cursor=json.dumps(obj=cursor))

    return _sensor

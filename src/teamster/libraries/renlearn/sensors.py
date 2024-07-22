import json
import re
from collections import defaultdict
from itertools import groupby
from operator import itemgetter

import pendulum
from dagster import (
    AssetKey,
    AssetsDefinition,
    MultiPartitionKey,
    MultiPartitionsDefinition,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    _check,
    define_asset_job,
    sensor,
)

from teamster.libraries.ssh.resources import SSHResource


def build_renlearn_sftp_sensor(
    code_location: str,
    asset_selection: list[AssetsDefinition],
    partition_key_start_date: str,
    timezone,
    minimum_interval_seconds=None,
    tags=None,
):
    base_job_name = f"{code_location}_renlearn_sftp_asset_job"

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
    def _sensor(context: SensorEvaluationContext, ssh_renlearn: SSHResource):
        now_timestamp = pendulum.now(tz=timezone).timestamp()

        run_request_kwargs = []
        run_requests = []
        cursor: dict = json.loads(context.cursor or "{}")

        files = ssh_renlearn.listdir_attr_r()

        for asset in asset_selection:
            asset_metadata = asset.metadata_by_key[asset.key]
            asset_identifier = asset.key.to_python_identifier()
            context.log.info(asset_identifier)

            last_run = cursor.get(asset_identifier, 0)

            partitions_def = _check.inst(
                asset.partitions_def, MultiPartitionsDefinition
            )

            subjects = partitions_def.get_partitions_def_for_dimension("subject")
            job_name = (
                f"{base_job_name}_{partitions_def.get_serializable_unique_identifier()}"
            )

            for f, _ in files:
                match = re.match(
                    pattern=asset_metadata["remote_file_regex"], string=f.filename
                )

                if (
                    match is not None
                    and f.st_mtime > last_run
                    and _check.not_none(value=f.st_size) > 0
                ):
                    context.log.info(f"{f.filename}: {f.st_mtime} - {f.st_size}")
                    for subject in subjects.get_partition_keys():
                        run_request_kwargs.append(
                            {
                                "asset_key": asset.key,
                                "job_name": job_name,
                                "partition_key": MultiPartitionKey(
                                    {
                                        "start_date": partition_key_start_date,
                                        "subject": subject,
                                    }
                                ),
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

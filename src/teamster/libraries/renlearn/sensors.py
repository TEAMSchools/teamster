import json
import re
from collections import defaultdict
from datetime import datetime
from itertools import groupby
from operator import itemgetter
from zoneinfo import ZoneInfo

from dagster import (
    AssetKey,
    AssetsDefinition,
    MultiPartitionKey,
    MultiPartitionsDefinition,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    define_asset_job,
    sensor,
)
from dagster_shared import check

from teamster.libraries.ssh.resources import SSHResource


def build_renlearn_sftp_sensor(
    code_location: str,
    timezone: ZoneInfo,
    asset_selection: list[AssetsDefinition],
    partition_key_start_date: str,
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
        now_timestamp = datetime.now(timezone).timestamp()

        run_request_kwargs = []
        run_requests = []
        cursor: dict = json.loads(context.cursor or "{}")

        files = ssh_renlearn.listdir_attr_r()

        for asset in asset_selection:
            asset_metadata = asset.metadata_by_key[asset.key]
            asset_identifier = asset.key.to_python_identifier()
            context.log.info(asset_identifier)

            last_run = cursor.get(asset_identifier, 0)

            partitions_def = check.inst(asset.partitions_def, MultiPartitionsDefinition)

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
                    and check.not_none(value=f.st_size) > 0
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

        item_getter_key = itemgetter("job_name", "partition_key")

        for (job_name, partition_key), group in groupby(
            iterable=sorted(run_request_kwargs, key=item_getter_key),
            key=item_getter_key,
        ):
            foo = [g["asset_key"] for g in group]
            run_requests.append(
                RunRequest(
                    run_key=f"{job_name}_{partition_key}_{now_timestamp}",
                    job_name=job_name,
                    partition_key=partition_key,
                    asset_selection=foo,
                )
            )

        return SensorResult(run_requests=run_requests, cursor=json.dumps(obj=cursor))

    return _sensor

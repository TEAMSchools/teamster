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
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    define_asset_job,
    sensor,
)
from dagster_shared import check

from teamster.libraries.ssh.resources import SSHResource


def build_amplify_mclass_sftp_sensor(
    code_location: str,
    timezone: ZoneInfo,
    asset_selection: list[AssetsDefinition],
    remote_dir_regex: str,
    minimum_interval_seconds: int | None = None,
):
    base_job_name = f"{code_location}__amplify__mclass__sftp_asset_job"

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
    def _sensor(context: SensorEvaluationContext, ssh_amplify: SSHResource):
        now_timestamp = datetime.now(timezone).timestamp()

        run_request_kwargs = []
        run_requests = []
        cursor: dict = json.loads(context.cursor or "{}")

        files = ssh_amplify.listdir_attr_r(remote_dir=remote_dir_regex)

        for asset in asset_selection:
            asset_identifier = asset.key.to_python_identifier()
            metadata_by_key = asset.metadata_by_key[asset.key]
            partitions_def = check.not_none(value=asset.partitions_def)
            context.log.info(asset_identifier)

            last_run = cursor.get(asset_identifier, 0)

            pattern = re.compile(
                pattern=(
                    rf"{metadata_by_key['remote_dir_regex']}/"
                    rf"{metadata_by_key['remote_file_regex']}"
                )
            )

            file_matches = [
                (f, path)
                for f, path in files
                if pattern.match(string=path)
                and check.not_none(value=f.st_mtime) > last_run
                and check.not_none(value=f.st_size) > 0
            ]

            for f, path in file_matches:
                match = check.not_none(value=pattern.match(string=path))

                partition_key = MultiPartitionKey(match.groupdict())

                context.log.info(f"{f.filename}: {partition_key}")
                run_request_kwargs.append(
                    {
                        "asset_key": asset.key,
                        "partition_key": partition_key,
                        "job_name": (
                            f"{base_job_name}_"
                            f"{partitions_def.get_serializable_unique_identifier()}"
                        ),
                    }
                )

                cursor[asset_identifier] = now_timestamp

        item_getter_key = itemgetter("job_name", "partition_key")

        for (job_name, partition_key), group in groupby(
            iterable=sorted(run_request_kwargs, key=item_getter_key),
            key=item_getter_key,
        ):
            run_requests.append(
                RunRequest(
                    run_key=f"{job_name}_{partition_key}_{now_timestamp}",
                    job_name=job_name,
                    partition_key=partition_key,
                    asset_selection=[g["asset_key"] for g in group],
                )
            )

        return SensorResult(run_requests=run_requests, cursor=json.dumps(obj=cursor))

    return _sensor

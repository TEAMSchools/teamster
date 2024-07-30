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
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    _check,
    define_asset_job,
    sensor,
)

from teamster.libraries.ssh.resources import SSHResource


def build_iready_sftp_sensor(
    code_location: str,
    asset_selection: list[AssetsDefinition],
    timezone,
    remote_dir_regex: str,
    current_fiscal_year: int,
    minimum_interval_seconds=None,
):
    base_job_name = f"{code_location}_iready_sftp_asset_job"

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
    def _sensor(context: SensorEvaluationContext, ssh_iready: SSHResource):
        now_timestamp = pendulum.now(tz=timezone).timestamp()

        run_request_kwargs = []
        run_requests = []
        cursor: dict = json.loads(context.cursor or "{}")

        files = ssh_iready.listdir_attr_r(remote_dir=remote_dir_regex)

        for asset in asset_selection:
            asset_identifier = asset.key.to_python_identifier()
            metadata_by_key = asset.metadata_by_key[asset.key]
            partitions_def = _check.not_none(value=asset.partitions_def)
            context.log.info(asset_identifier)

            last_run = cursor.get(asset_identifier, 0)

            pattern = re.compile(
                pattern=(
                    rf"{metadata_by_key["remote_dir_regex"]}/"
                    rf"{metadata_by_key["remote_file_regex"]}"
                )
            )

            file_matches = [
                (f, path)
                for f, path in files
                if pattern.match(string=path)
                and _check.not_none(value=f.st_mtime) > last_run
                and _check.not_none(value=f.st_size) > 0
            ]

            for f, path in file_matches:
                match = _check.not_none(value=pattern.match(string=path))

                group_dict = match.groupdict()

                if group_dict["academic_year"] == "Current_Year":
                    partition_key = MultiPartitionKey(
                        {
                            "academic_year": str(current_fiscal_year - 1),
                            "subject": group_dict["subject"],
                        }
                    )
                else:
                    partition_key = MultiPartitionKey(group_dict)

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

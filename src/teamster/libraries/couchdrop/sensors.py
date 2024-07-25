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
    SkipReason,
    StaticPartitionsDefinition,
    _check,
    define_asset_job,
    sensor,
)
from paramiko.ssh_exception import AuthenticationException, SSHException

from teamster.libraries.ssh.resources import SSHResource


def build_couchdrop_sftp_sensor(
    code_location,
    local_timezone,
    asset_selection: list[AssetsDefinition],
    minimum_interval_seconds: int,
    exclude_dirs: list | None = None,
):
    if exclude_dirs is None:
        exclude_dirs = []

    base_job_name = f"{code_location}_couchdrop_sftp_asset_job"

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
    def _sensor(context: SensorEvaluationContext, ssh_couchdrop: SSHResource):
        now_timestamp = pendulum.now(tz=local_timezone).timestamp()

        run_request_kwargs = []
        run_requests = []
        tick_cursor = float(context.cursor or "0.0")

        try:
            files = ssh_couchdrop.listdir_attr_r(
                remote_dir=f"/data-team/{code_location}", exclude_dirs=exclude_dirs
            )
        except (SSHException, AuthenticationException) as e:
            if (
                isinstance(e, SSHException)
                and "Error reading SSH protocol banner" in e.args
            ):
                context.log.error(msg=str(e))
                return SkipReason(str(e))
            elif (
                isinstance(e, AuthenticationException)
                and "Authentication timeout" in e.args
            ):
                context.log.error(msg=str(e))
                return SkipReason(str(e))
            else:
                raise e
        except Exception as e:
            context.log.error(msg=str(e))
            raise e

        for a in asset_selection:
            asset_identifier = a.key.to_python_identifier()
            metadata_by_key = a.metadata_by_key[a.key]
            partitions_def = _check.not_none(value=a.partitions_def)
            context.log.info(asset_identifier)

            pattern = re.compile(
                pattern=(
                    f"{metadata_by_key["remote_dir_regex"]}/"
                    f"{metadata_by_key["remote_file_regex"]}"
                )
            )

            file_matches = [
                (f, path)
                for f, path in files
                if pattern.match(string=path)
                and _check.not_none(value=f.st_mtime) > tick_cursor
                and _check.not_none(value=f.st_size) > 0
            ]

            for f, path in file_matches:
                match = _check.not_none(value=pattern.match(string=path))

                if isinstance(a.partitions_def, MultiPartitionsDefinition):
                    partition_key = MultiPartitionKey(match.groupdict())
                elif isinstance(a.partitions_def, StaticPartitionsDefinition):
                    partition_key = match.group(1)
                else:
                    partition_key = None

                context.log.info(f"{f.filename}: {partition_key}")
                run_request_kwargs.append(
                    {
                        "asset_key": a.key,
                        "job_name": (
                            f"{base_job_name}_"
                            f"{partitions_def.get_serializable_unique_identifier()}"
                        ),
                        "partition_key": partition_key,
                    }
                )

        if run_request_kwargs:
            tick_cursor = now_timestamp

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

        return SensorResult(run_requests=run_requests, cursor=str(tick_cursor))

    return _sensor

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
    SkipReason,
    define_asset_job,
    sensor,
)
from dagster_shared import check

from teamster.libraries.iready.subjects import is_legacy_year, partition_subject
from teamster.libraries.ssh.resources import SSHResource


def build_iready_sftp_sensor(
    code_location: str,
    timezone: ZoneInfo,
    asset_selection: list[AssetsDefinition],
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
        now_timestamp = datetime.now(timezone).timestamp()

        run_request_kwargs = []
        run_requests = []
        cursor: dict = json.loads(context.cursor or "{}")

        files = ssh_iready.listdir_attr_r_or_skip(remote_dir=remote_dir_regex)

        if isinstance(files, SkipReason):
            return files

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

            # Archive folders still hold pre-rename filenames. The current-era
            # pattern above can no longer match them for an asset whose
            # filename prefix changed outright (diagnostic_results), so also
            # try the legacy pattern -- but only accept a legacy match for a
            # legacy academic year. Without that gate, a stale pre-rename file
            # left behind in Current_Year (this happened on 2026-07-18) would
            # match the legacy pattern too and fire a spurious run.
            legacy_remote_file_regex = metadata_by_key["legacy_remote_file_regex"]

            legacy_pattern = (
                re.compile(
                    pattern=(
                        rf"{metadata_by_key['remote_dir_regex']}/"
                        rf"{legacy_remote_file_regex}"
                    )
                )
                if legacy_remote_file_regex
                else None
            )

            file_matches = []

            for f, path in files:
                if (
                    check.not_none(value=f.st_mtime) <= last_run
                    or check.not_none(value=f.st_size) <= 0
                ):
                    continue

                match = pattern.match(string=path)

                if match is None and legacy_pattern is not None:
                    legacy_match = legacy_pattern.match(string=path)

                    if legacy_match is not None and is_legacy_year(
                        academic_year=legacy_match.groupdict()["academic_year"]
                    ):
                        match = legacy_match

                if match is not None:
                    file_matches.append((f, path, match))

            for f, _, match in file_matches:
                group_dict = match.groupdict()

                # The regex alternation carries the vendor's current token
                # (`reading`); the partition space does not. Translate back
                # before building the key, or the RunRequest names a partition
                # that does not exist.
                subject_key = partition_subject(
                    remote_token=group_dict["subject"],
                    academic_year=group_dict["academic_year"],
                )

                if group_dict["academic_year"] == "Current_Year":
                    partition_key = MultiPartitionKey(
                        {
                            "academic_year": str(current_fiscal_year - 1),
                            "subject": subject_key,
                        }
                    )
                else:
                    partition_key = MultiPartitionKey(
                        {
                            "academic_year": group_dict["academic_year"],
                            "subject": subject_key,
                        }
                    )

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

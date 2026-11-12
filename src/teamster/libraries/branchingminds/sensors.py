import json
import re
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from dagster import (
    AssetKey,
    AssetsDefinition,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    SkipReason,
    define_asset_job,
    sensor,
)
from dagster_shared import check

from teamster.core.utils.classes import FiscalYear
from teamster.libraries.ssh.resources import SSHResource


def build_branchingminds_sftp_sensor(
    code_location: str,
    timezone: ZoneInfo,
    asset_selection: list[AssetsDefinition],
    remote_dir: str,
    minimum_interval_seconds: int | None = None,
):
    """Build one sensor over every Branching Minds export asset.

    Each export is a fixed-name file that BrM overwrites nightly, so a file's
    fiscal-year partition comes from its mtime in ``timezone``: BrM rolls its
    export window on July 1, and several exports carry no school-year column
    to read it from. The cursor holds each asset's max matched mtime.
    """
    job = define_asset_job(
        name=f"{code_location}__branchingminds__sftp_asset_job",
        selection=asset_selection,
    )

    @sensor(
        name=f"{code_location}__branchingminds__sftp_sensor",
        job=job,
        minimum_interval_seconds=minimum_interval_seconds,
    )
    def _sensor(context: SensorEvaluationContext, ssh_branchingminds: SSHResource):
        cursor: dict[str, float] = json.loads(context.cursor or "{}")
        keys_by_partition = defaultdict[str, set[AssetKey]](set)
        mtime_by_partition = defaultdict[str, float](float)

        files = ssh_branchingminds.listdir_attr_r_or_skip(remote_dir=remote_dir)

        if isinstance(files, SkipReason):
            return files

        for asset in asset_selection:
            asset_identifier = asset.key.to_python_identifier()
            metadata = asset.metadata_by_key[asset.key]
            remote_path_regex = (
                f"{metadata['remote_dir_regex']}/{metadata['remote_file_regex']}"
            )
            partitions_def = check.not_none(asset.partitions_def)
            last_mtime = cursor.get(asset_identifier, 0)

            for f, path in files:
                mtime = check.not_none(f.st_mtime)

                if (
                    re.fullmatch(pattern=remote_path_regex, string=path) is None
                    or mtime <= last_mtime
                    or check.not_none(f.st_size) == 0
                ):
                    continue

                partition_key = FiscalYear(
                    datetime=datetime.fromtimestamp(mtime, tz=timezone), start_month=7
                ).start.isoformat()

                if not partitions_def.has_partition_key(partition_key):
                    context.log.warning(
                        f"{f.filename}: {partition_key} is outside the partitions "
                        "definition; skipping"
                    )
                    continue

                context.log.info(f"{f.filename}: {mtime} -> {partition_key}")
                keys_by_partition[partition_key].add(asset.key)
                mtime_by_partition[partition_key] = max(
                    mtime_by_partition[partition_key], mtime
                )
                cursor[asset_identifier] = max(cursor.get(asset_identifier, 0), mtime)

        run_requests = [
            RunRequest(
                run_key=f"{job.name}_{partition_key}_{mtime_by_partition[partition_key]}",
                partition_key=partition_key,
                asset_selection=sorted(keys, key=lambda k: k.to_user_string()),
            )
            for partition_key, keys in keys_by_partition.items()
        ]

        return SensorResult(run_requests=run_requests, cursor=json.dumps(cursor))

    return _sensor

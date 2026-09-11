import csv
import io
import json
import re
import tempfile
import zipfile
from collections import defaultdict
from datetime import datetime
from itertools import groupby
from operator import itemgetter
from pathlib import Path
from zoneinfo import ZoneInfo

from dagster import (
    AssetKey,
    AssetsDefinition,
    MultiPartitionKey,
    MultiPartitionsDefinition,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    SkipReason,
    define_asset_job,
    sensor,
)
from dagster_shared import check

from teamster.libraries.ssh.resources import SSHResource


def _school_year_start_date(ssh: SSHResource, remote_filepath: str) -> str | None:
    """Read the school year out of the archive and return its fiscal-year key.

    Renaissance publishes one fixed-name archive holding a single school year,
    so the archive's own ``SchoolYear`` column -- not the wall clock -- says
    which fiscal-year partition the drop belongs to. ``"2026-2027"`` maps to
    the ``2026-07-01`` key, i.e. ``_dagster_partition_fiscal_year=2027``.

    Returns None when no member carries a populated ``SchoolYear``, leaving the
    caller to fall back to its configured partition key.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        local_filepath = ssh.sftp_get(
            remote_filepath=remote_filepath,
            local_filepath=str(Path(tmp_dir) / Path(remote_filepath).name),
        )

        with zipfile.ZipFile(local_filepath) as zip_file:
            for info in zip_file.infolist():
                if info.file_size == 0:
                    continue

                with zip_file.open(info) as member:
                    reader = csv.DictReader(io.TextIOWrapper(member, encoding="utf-8"))

                    row = next(reader, None)

                if row is None:
                    continue

                school_year = next(
                    (
                        value
                        for key, value in row.items()
                        if key is not None and key.lower() == "schoolyear" and value
                    ),
                    None,
                )

                if school_year is not None:
                    return f"{school_year.split('-')[0]}-07-01"

    return None


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

        # one archive is shared by every asset, so peek it once per evaluation
        start_date_by_remote_filepath: dict[str, str | None] = {}

        files = ssh_renlearn.listdir_attr_r_or_skip()

        if isinstance(files, SkipReason):
            return files

        for asset in asset_selection:
            asset_metadata = asset.metadata_by_key[asset.key]
            asset_identifier = asset.key.to_python_identifier()
            context.log.info(asset_identifier)

            last_run = cursor.get(asset_identifier, 0)

            partitions_def = check.inst(asset.partitions_def, MultiPartitionsDefinition)

            subjects = partitions_def.get_partitions_def_for_dimension("subject")
            start_dates = partitions_def.get_partitions_def_for_dimension("start_date")
            job_name = (
                f"{base_job_name}_{partitions_def.get_serializable_unique_identifier()}"
            )

            for f, path in files:
                match = re.match(
                    pattern=asset_metadata["remote_file_regex"], string=f.filename
                )

                if (
                    match is not None
                    and f.st_mtime > last_run
                    and check.not_none(value=f.st_size) > 0
                ):
                    context.log.info(f"{f.filename}: {f.st_mtime} - {f.st_size}")

                    # advance the cursor even if the drop is skipped below, so a
                    # year we cannot place is not re-downloaded every tick
                    cursor[asset_identifier] = now_timestamp

                    if path not in start_date_by_remote_filepath:
                        start_date_by_remote_filepath[path] = _school_year_start_date(
                            ssh=ssh_renlearn, remote_filepath=path
                        )

                    start_date = start_date_by_remote_filepath[path]

                    if start_date is None:
                        context.log.warning(
                            f"{path}: found no SchoolYear, falling back to "
                            f"{partition_key_start_date}"
                        )
                        start_date = partition_key_start_date
                    elif start_date not in start_dates.get_partition_keys():
                        context.log.warning(
                            f"{path}: SchoolYear resolves to {start_date}, which is "
                            "outside the partitions definition; skipping"
                        )
                        continue

                    for subject in subjects.get_partition_keys():
                        run_request_kwargs.append(
                            {
                                "asset_key": asset.key,
                                "job_name": job_name,
                                "partition_key": MultiPartitionKey(
                                    {
                                        "start_date": start_date,
                                        "subject": subject,
                                    }
                                ),
                            }
                        )

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

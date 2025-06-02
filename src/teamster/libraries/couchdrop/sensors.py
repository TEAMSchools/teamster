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
    StaticPartitionsDefinition,
    define_asset_job,
    sensor,
)
from dagster_shared import check

from teamster.libraries.google.drive.resources import GoogleDriveResource


def build_couchdrop_sftp_sensor(
    code_location: str,
    local_timezone: ZoneInfo,
    asset_selection: list[AssetsDefinition],
    minimum_interval_seconds: int,
    folder_id: str,
    exclude_dirs: list | None = None,
):
    if exclude_dirs is None:
        exclude_dirs = []

    base_job_name = f"{code_location}__couchdrop__sftp_asset_job"

    keys_by_partitions_def = defaultdict(set[AssetKey])

    for assets_def in asset_selection:
        keys_by_partitions_def[assets_def.partitions_def].add(assets_def.key)

    jobs = [
        define_asset_job(
            name=(
                f"{base_job_name}_{partitions_def.get_serializable_unique_identifier()}"
                if partitions_def is not None
                else base_job_name
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
    def _sensor(context: SensorEvaluationContext, google_drive: GoogleDriveResource):
        now_timestamp = datetime.now(local_timezone).timestamp()

        run_request_kwargs = []
        run_requests = []

        cursor: dict = json.loads(context.cursor or "{}")

        files = google_drive.files_list_recursive(
            corpora="drive",
            drive_id="0AKZ2G1Z8rxooUk9PVA",
            include_items_from_all_drives=True,
            supports_all_drives=True,
            fields="id,name,mimeType,modifiedTime,size",
            folder_id=folder_id,
            file_path=f"/data-team/{code_location}",
            exclude=exclude_dirs,
        )

        for a in asset_selection:
            asset_identifier = a.key.to_python_identifier()
            metadata = a.metadata_by_key[a.key]

            max_modified_timestamp = cursor_modified_timestamp = cursor.get(
                asset_identifier, 0
            )

            pattern = re.compile(
                pattern=(
                    rf"{metadata['remote_dir_regex']}/{metadata['remote_file_regex']}"
                )
            )

            file_matches = [
                f
                for f in files
                if pattern.match(string=f["path"])
                and f["modified_timestamp"] > cursor_modified_timestamp
                and f["size"] > 0
            ]

            for f in file_matches:
                if f["modified_timestamp"] > max_modified_timestamp:
                    max_modified_timestamp = f["modified_timestamp"]

                match = check.not_none(value=pattern.match(string=f["path"]))

                if isinstance(a.partitions_def, MultiPartitionsDefinition):
                    partition_key = MultiPartitionKey(match.groupdict())
                elif isinstance(a.partitions_def, StaticPartitionsDefinition):
                    partition_key = match.group(1)
                else:
                    partition_key = None

                context.log.info(f"{asset_identifier}\n{f['name']}: {partition_key}")

                if a.partitions_def is not None:
                    run_request_kwargs.append(
                        {
                            "asset_key": a.key,
                            "job_name": (
                                f"{base_job_name}_"
                                + a.partitions_def.get_serializable_unique_identifier()
                            ),
                            "partition_key": partition_key,
                        }
                    )
                else:
                    run_request_kwargs.append(
                        {
                            "asset_key": a.key,
                            "job_name": base_job_name,
                            "partition_key": None,
                        }
                    )

            cursor[asset_identifier] = max_modified_timestamp

        if run_request_kwargs:
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

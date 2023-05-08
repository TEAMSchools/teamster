import json
import pathlib
import re

import pendulum
from dagster import (
    AssetsDefinition,
    AssetSelection,
    MultiPartitionKey,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    sensor,
)
from dagster_ssh import SSHResource

from teamster.core.utils.classes import FiscalYear


def build_sftp_sensor(
    code_location,
    source_system,
    asset_defs: list[AssetsDefinition],
    minimum_interval_seconds=None,
):
    @sensor(
        name=f"{code_location}_{source_system}_sftp_sensor",
        minimum_interval_seconds=minimum_interval_seconds,
        asset_selection=AssetSelection.assets(*asset_defs),
        required_resource_keys={f"sftp_{source_system}"},
    )
    def _sensor(context: SensorEvaluationContext):
        now = pendulum.now()
        cursor: dict = json.loads(context.cursor or "{}")

        sftp: SSHResource = getattr(context.resources, f"sftp_{source_system}")

        ls = []
        conn = sftp.get_connection()
        with conn.open_sftp() as sftp_client:
            for asset in asset_defs:
                for path in asset.metadata_by_key[asset.key]["remote_filepath"]:
                    ls.append(
                        {
                            "asset": asset,
                            "remote_filepath": path,
                            "files": sftp_client.listdir_attr(path=path),
                        }
                    )
        conn.close()

        run_requests = []
        for filepath in ls:
            asset = filepath["asset"]
            files = filepath["files"]
            remote_filepath = pathlib.Path(filepath["remote_filepath"])

            asset_identifier = asset.key.to_python_identifier()

            last_run = cursor.get(asset_identifier, 0)

            asset_metadata = asset.metadata_by_key[asset.key]

            partition_keys = []
            for f in files:
                context.log.info(f"{f.filename}: {f.st_mtime} - {f.st_size}")

                match = re.match(
                    pattern=asset_metadata["remote_file_regex"], string=f.filename
                )

                if match is not None and f.st_mtime >= last_run and f.st_size > 0:
                    if remote_filepath.name == "Current_Year":
                        date_partition = FiscalYear(
                            datetime=pendulum.from_timestamp(timestamp=f.st_mtime),
                            start_month=7,
                        ).start.to_date_string()
                    else:
                        date_partition = f"{remote_filepath.name[-4:]}-07-01"

                    partition_keys.append(
                        MultiPartitionKey({**match.groupdict(), "date": date_partition})
                    )

            if partition_keys:
                for pk in partition_keys:
                    run_requests.append(
                        RunRequest(
                            run_key=f"{asset_identifier}_{pk}",
                            asset_selection=[asset.key],
                            partition_key=pk,
                        )
                    )

                cursor[asset_identifier] = now.timestamp()

        return SensorResult(run_requests=run_requests, cursor=json.dumps(obj=cursor))

    return _sensor

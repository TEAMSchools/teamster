import json
import re

import pendulum
from dagster import (
    AddDynamicPartitionsRequest,
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
from teamster.core.utils.variables import CURRENT_FISCAL_YEAR, NOW


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
        cursor: dict = json.loads(context.cursor or "{}")
        ssh: SSHResource = getattr(context.resources, f"sftp_{source_system}")

        ls = {}
        conn = ssh.get_connection()
        with conn.open_sftp() as sftp_client:
            for asset in asset_defs:
                ls[asset.key.to_python_identifier()] = {
                    "files": sftp_client.listdir_attr(
                        path=asset.metadata_by_key[asset.key]["remote_filepath"]
                    ),
                    "asset": asset,
                }
        conn.close()

        run_requests = []
        dynamic_partitions_requests = []
        for asset_identifier, asset_dict in ls.items():
            last_run = cursor.get(asset_identifier, 0)
            asset = asset_dict["asset"]
            files = asset_dict["files"]

            asset_metadata = asset.metadata_by_key[asset.key]

            updates = []
            for f in files:
                match = re.match(
                    pattern=asset_metadata["remote_file_regex"], string=f.filename
                )

                if match is not None:
                    context.log.info(f"{f.filename}: {f.st_mtime} - {f.st_size}")
                    if f.st_mtime > last_run and f.st_size > 0:
                        pass

            if updates:
                for run in updates:
                    # run requests
                    pass

            # dynamic partitions

            cursor[asset_identifier] = NOW.timestamp()

        return SensorResult(
            run_requests=run_requests,
            cursor=json.dumps(obj=cursor),
            dynamic_partitions_requests=dynamic_partitions_requests,
        )

    return _sensor


# dynamic_partitions_requests.append(
#     AddDynamicPartitionsRequest(
#         partitions_def_name=f"{asset_identifier}_date",
#         partition_keys=list(set([pk["date"] for pk in partition_keys])),
#     )
# )

# run_requests.append(
#     RunRequest(
#         run_key=f"{asset_identifier}_{f.st_mtime}",
#         asset_selection=[asset.key],
#         partition_key=CURRENT_FISCAL_YEAR.start.to_date_string(),
#     )
# )

# run_requests.append(
#     RunRequest(
#         run_key=f"{asset_identifier}_{f.st_mtime}",
#         asset_selection=[asset.key],
#         partition_key=pendulum.from_timestamp(
#             timestamp=f.st_mtime
#         ).to_date_string(),
#     )
# )

# run_requests.append(
#     RunRequest(
#         run_key=f"{asset_identifier}_{pk}",
#         asset_selection=[asset.key],
#         partition_key=MultiPartitionKey(pk),
#     )
# )

# run_requests.append(
#     RunRequest(
#         run_key=f"{asset_identifier}_{run['mtime']}",
#         asset_selection=[asset.key],
#         partition_key=run["partition_key"],
#     )
# )

# updates.append(
#     {
#         "mtime": f.st_mtime,
#         "partition_key": MultiPartitionKey(
#             {
#                 **match.groupdict(),
#                 "date": FiscalYear(
#                     datetime=pendulum.from_timestamp(timestamp=f.st_mtime),
#                     start_month=7,
#                 ).start.to_date_string(),
#             }
#         ),
#     }
# )

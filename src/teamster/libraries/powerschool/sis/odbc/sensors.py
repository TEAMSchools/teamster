"""PowerSchool SIS ODBC asset sensor.

Defines a Dagster sensor that evaluates PowerSchool assets for staleness
and returns a SensorResult with RunRequests for stale assets grouped by
job name and partition key.
"""

from collections import defaultdict
from datetime import datetime
from itertools import groupby
from operator import itemgetter
from zoneinfo import ZoneInfo

from dagster import (
    AssetKey,
    AssetsDefinition,
    PartitionsDefinition,
    RunRequest,
    SensorDefinition,
    SensorEvaluationContext,
    SensorResult,
    define_asset_job,
    sensor,
)

from teamster.libraries.powerschool.sis.odbc.resources import PowerSchoolODBCResource
from teamster.libraries.powerschool.sis.odbc.utils import (
    evaluate_asset_staleness,
    powerschool_connection,
)
from teamster.libraries.ssh.resources import SSHResource


def build_powerschool_asset_sensor(
    code_location: str,
    execution_timezone: ZoneInfo,
    asset_selection: list[AssetsDefinition],
    minimum_interval_seconds: int | None = None,
) -> SensorDefinition:
    """Build a Dagster sensor that detects and rematerializes stale assets.

    Args:
        code_location: District code location identifier.
        execution_timezone: Timezone for sensor evaluation.
        asset_selection: Assets to monitor for staleness.
        minimum_interval_seconds: Minimum seconds between sensor ticks.

    Returns:
        A Dagster sensor function.
    """
    jobs = []
    keys_by_partitions_def: defaultdict[PartitionsDefinition | None, set[AssetKey]] = (
        defaultdict(set)
    )

    base_job_name = f"{code_location}__powerschool__sis__asset_job"

    for assets_def in asset_selection:
        keys_by_partitions_def[assets_def.partitions_def].add(assets_def.key)

    for partitions_def, keys in keys_by_partitions_def.items():
        if partitions_def is None:
            job_name = f"{base_job_name}_None"
        else:
            job_name = (
                f"{base_job_name}_{partitions_def.get_serializable_unique_identifier()}"
            )

        jobs.append(define_asset_job(name=job_name, selection=list(keys)))

    @sensor(
        name=f"{base_job_name}_sensor",
        jobs=jobs,
        minimum_interval_seconds=minimum_interval_seconds,
    )
    def _sensor(
        context: SensorEvaluationContext,
        ssh_powerschool: SSHResource,
        db_powerschool: PowerSchoolODBCResource,
    ) -> SensorResult:
        with powerschool_connection(
            ssh_powerschool, db_powerschool, context.log
        ) as connection:
            results = evaluate_asset_staleness(
                asset_selection=asset_selection,
                execution_timezone=execution_timezone,
                instance=context.instance,
                connection=connection,
                db_powerschool=db_powerschool,
                log=context.log,
                limit_monthly_partitions=None,
            )

        kwargs = []
        for r in results:
            if r.partitions_def_identifier is None:
                job_name = f"{base_job_name}_None"
            else:
                job_name = f"{base_job_name}_{r.partitions_def_identifier}"

            kwargs.append(
                {
                    "asset_key": r.asset_key,
                    "job_name": job_name,
                    "partition_key": r.partition_key or "",
                }
            )

        run_requests = []
        item_getter = itemgetter("job_name", "partition_key")

        for (job_name, partition_key), group in groupby(
            iterable=sorted(kwargs, key=item_getter), key=item_getter
        ):
            run_requests.append(
                RunRequest(
                    run_key=(
                        f"{job_name}_{partition_key}_{datetime.now().timestamp()}"
                    ),
                    job_name=job_name,
                    partition_key=partition_key or None,
                    asset_selection=[g["asset_key"] for g in group],
                )
            )

        return SensorResult(run_requests=run_requests)

    return _sensor

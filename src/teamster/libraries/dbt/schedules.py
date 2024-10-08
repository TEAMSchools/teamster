from dagster import (
    AssetsDefinition,
    RunRequest,
    ScheduleEvaluationContext,
    define_asset_job,
    schedule,
)


def build_dbt_code_version_schedule(
    code_location, cron_schedule, execution_timezone, dbt_assets: AssetsDefinition
):
    job = define_asset_job(
        name=f"{code_location}__dbt__code_version_job", selection=[dbt_assets]
    )

    @schedule(
        name=f"{job.name}_schedule",
        cron_schedule=cron_schedule,
        execution_timezone=execution_timezone,
        job=job,
    )
    def _schedule(context: ScheduleEvaluationContext):
        asset_selection = []

        latest_code_versions = (
            context.instance.get_latest_materialization_code_versions(
                asset_keys=dbt_assets.keys
            )
        )

        for asset_key, current_code_version in dbt_assets.code_versions_by_key.items():
            latest_code_version = latest_code_versions.get(asset_key)

            if current_code_version != latest_code_version:
                asset_selection.append(asset_key)

        if asset_selection:
            return RunRequest(asset_selection=asset_selection)

    return _schedule

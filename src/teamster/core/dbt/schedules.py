from dagster import (
    AssetsDefinition,
    AssetSelection,
    RunRequest,
    ScheduleEvaluationContext,
    define_asset_job,
    schedule,
)


def build_dbt_code_version_schedule(
    code_location, cron_schedule, execution_timezone, dbt_assets: AssetsDefinition
):
    job_name = f"{code_location}_dbt_code_version_job"

    schedule_name = f"{job_name}_schedule"

    @schedule(
        cron_schedule=cron_schedule,
        name=schedule_name,
        execution_timezone=execution_timezone,
        job=define_asset_job(
            name=job_name, selection=AssetSelection.assets(dbt_assets)
        ),
    )
    def _schedule(context: ScheduleEvaluationContext):
        latest_code_versions = (
            context.instance.get_latest_materialization_code_versions(
                asset_keys=list(dbt_assets.code_versions_by_key.keys())
            )
        )

        asset_selection = []
        for asset_key, current_code_version in dbt_assets.code_versions_by_key.items():
            latest_code_version = latest_code_versions.get(asset_key)

            if current_code_version != latest_code_version:
                asset_selection.append(asset_key)

        if asset_selection:
            return RunRequest(run_key=schedule_name, asset_selection=asset_selection)

    return _schedule

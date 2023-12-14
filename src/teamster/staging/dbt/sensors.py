from dagster import (
    AssetSelection,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    sensor,
)

from .assets import _dbt_assets

_dbt_assets.code_versions_by_key


@sensor(asset_selection=AssetSelection.assets(_dbt_assets))
def dbt_code_version_sensor(context: SensorEvaluationContext):
    latest_code_versions = context.instance.get_latest_materialization_code_versions(
        asset_keys=list(_dbt_assets.code_versions_by_key.keys())
    )

    asset_selection = []
    for asset_key, current_code_version in _dbt_assets.code_versions_by_key.items():
        latest_code_version = latest_code_versions.get(asset_key)

        if current_code_version != latest_code_version:
            asset_selection.append(asset_key)

    return SensorResult(run_requests=[RunRequest(asset_selection=asset_selection)])


_all = [
    dbt_code_version_sensor,
]

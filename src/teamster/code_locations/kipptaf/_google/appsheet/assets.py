from dagster import AssetSpec

from teamster.code_locations.kipptaf._dbt.assets import manifest

asset_specs = [
    AssetSpec(
        key=source["meta"]["dagster"]["asset_key"],
        metadata={
            "dataset_id": source["schema"],
            "table_id": source.get("identifier") or source["name"],
        },
        group_name="google_appsheet",
        kinds={"bigquery"},
    )
    for source in manifest["sources"].values()
    if source["source_name"] == "google_appsheet"
]

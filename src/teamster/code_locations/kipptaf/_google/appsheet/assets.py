from dagster import AssetSpec, external_assets_from_specs

from teamster.code_locations.kipptaf._dbt.assets import manifest

specs = [
    AssetSpec(
        key=source["meta"]["dagster"]["asset_key"],
        metadata={"dataset_id": source["schema"], "table_id": source["name"]},
        group_name="google_appsheet",
    )
    for source in manifest["sources"].values()
    if source["source_name"] == "google_appsheet" and "retired" not in source["tags"]
]

google_appsheet_assets = external_assets_from_specs(specs=specs)

assets = [
    *google_appsheet_assets,
]

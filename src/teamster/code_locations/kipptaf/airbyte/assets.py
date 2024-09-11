import pathlib

from dagster import AssetKey, AssetSpec, config_from_files

from teamster.code_locations.kipptaf import CODE_LOCATION

config_dir = pathlib.Path(__file__).parent

assets = [
    AssetSpec(
        key=AssetKey([CODE_LOCATION, a["group_name"], table]),
        metadata={
            "connection_id": a["connection_id"],
            "dataset_id": a["dataset_id"],
            "table_id": table,
        },
        group_name=a["group_name"],
    )
    for a in config_from_files([f"{config_dir}/config/assets.yaml"])["assets"]
    for table in a["destination_tables"]
]

from dagster import config_from_files

from teamster.core.deanslist.assets import build_deanslist_endpoint_asset
from teamster.test import CODE_LOCATION

config = config_from_files(
    [f"src/teamster/{CODE_LOCATION}/deanslist/config/assets.yaml"]
)
school_ids = config["school_ids"]

nonpartition_assets = [
    build_deanslist_endpoint_asset(
        code_location=CODE_LOCATION, school_ids=school_ids, **endpoint
    )
    for endpoint in config["endpoints"]
]

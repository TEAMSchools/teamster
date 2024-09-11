from teamster import GCS_PROJECT_NAME
from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.fivetran.assets import asset_specs
from teamster.libraries.fivetran.sensors import (
    build_fivetran_connector_sync_status_sensor,
)

fivetran_connector_sync_status_sensor = build_fivetran_connector_sync_status_sensor(
    code_location=CODE_LOCATION,
    minimum_interval_seconds=(60 * 5),
    asset_selection=asset_specs,
    project=GCS_PROJECT_NAME,
)

sensors = [
    fivetran_connector_sync_status_sensor,
]

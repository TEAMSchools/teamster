from dagster import Definitions, load_assets_from_modules

from teamster.core.resources import get_io_manager_gcs_avro
from teamster.staging import CODE_LOCATION

from . import assets

defs = Definitions(
    assets=load_assets_from_modules(
        modules=[
            assets,
        ]
    ),
    sensors=[],
    schedules=[],
    resources={
        "io_manager_gcs_avro": get_io_manager_gcs_avro(CODE_LOCATION),
    },
)

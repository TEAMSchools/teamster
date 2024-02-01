from dagster import Definitions, load_assets_from_modules

from teamster.core.resources import BIGQUERY_RESOURCE, get_io_manager_gcs_avro
from teamster.kipptaf import performance_management
from teamster.staging import CODE_LOCATION

defs = Definitions(
    assets=load_assets_from_modules(
        modules=[
            performance_management,
        ]
    ),
    sensors=[],
    schedules=[],
    resources={
        "io_manager_gcs_avro": get_io_manager_gcs_avro(CODE_LOCATION),
        "db_bigquery": BIGQUERY_RESOURCE,
    },
)

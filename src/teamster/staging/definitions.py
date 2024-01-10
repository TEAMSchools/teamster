from dagster import Definitions, load_assets_from_modules

from teamster.core.resources import get_io_manager_gcs_avro
from teamster.kipptaf import airbyte, fivetran
from teamster.staging import CODE_LOCATION, resources

defs = Definitions(
    assets=load_assets_from_modules(
        modules=[
            airbyte,
            fivetran,
        ]
    ),
    sensors=[
        *airbyte.sensors,
        *fivetran.sensors,
    ],
    schedules=[
        *airbyte.schedules,
        *fivetran.schedules,
    ],
    resources={
        "io_manager_gcs_avro": get_io_manager_gcs_avro(CODE_LOCATION),
        "airbyte": resources.AIRBYTE_CLOUD_RESOURCE,
        "fivetran": resources.FIVETRAN_RESOURCE,
    },
)

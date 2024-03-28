from dagster import Definitions, load_assets_from_modules

from teamster.core.resources import get_io_manager_gcs_avro

from . import illuminate
from .resources import SLING_RESOURCE

defs = Definitions(
    assets=load_assets_from_modules(modules=[illuminate]),
    resources={
        "io_manager_gcs_avro": get_io_manager_gcs_avro("staging"),
        "sling": SLING_RESOURCE,
    },
)

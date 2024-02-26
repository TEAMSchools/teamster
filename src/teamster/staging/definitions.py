from dagster import Definitions, load_assets_from_modules

from teamster.core.resources import get_io_manager_gcs_avro
from teamster.kipptaf import tableau

from . import assets, resources

defs = Definitions(
    assets=load_assets_from_modules(
        modules=[
            assets,
            tableau,
        ]
    ),
    resources={
        "io_manager_gcs_avro": get_io_manager_gcs_avro("staging"),
        "tableau": resources.TABLEAU_SERVER_RESOURCE,
    },
)

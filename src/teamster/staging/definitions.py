from dagster import Definitions, EnvVar, load_assets_from_modules

from teamster.core.resources import get_io_manager_gcs_avro
from teamster.kipptaf import tableau
from teamster.kipptaf.tableau.resources import TableauServerResource

from . import assets

defs = Definitions(
    assets=load_assets_from_modules(
        modules=[
            assets,
            tableau,
        ]
    ),
    schedules=[
        *tableau.schedules,
    ],
    resources={
        "io_manager_gcs_avro": get_io_manager_gcs_avro("staging"),
        "tableau": TableauServerResource(
            server_address="https://tableau.kipp.org",
            site_id="KIPPNJ",
            token_name=EnvVar("TABLEAU_TOKEN_NAME"),
            personal_access_token=EnvVar("TABLEAU_PERSONAL_ACCESS_TOKEN"),
        ),
    },
)

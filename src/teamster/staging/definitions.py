from dagster import Definitions, load_assets_from_modules

from teamster.core.resources import get_io_manager_gcs_avro
from teamster.kipptaf import ldap, resources
from teamster.kipptaf.google import sheets
from teamster.staging import CODE_LOCATION

defs = Definitions(
    assets=load_assets_from_modules(
        modules=[
            ldap,
            sheets,
        ]
    ),
    sensors=[
        *sheets.sensors,
    ],
    resources={
        "io_manager_gcs_avro": get_io_manager_gcs_avro(CODE_LOCATION),
        "ldap": resources.LDAP_RESOURCE,
        "gsheets": resources.GOOGLE_SHEETS_RESOURCE,
    },
)

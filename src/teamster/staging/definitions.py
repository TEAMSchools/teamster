from dagster import Definitions, load_assets_from_modules

from teamster.core.resources import get_io_manager_gcs_avro
from teamster.kipptaf import ldap
from teamster.kipptaf.resources import LDAP_RESOURCE
from teamster.staging import CODE_LOCATION

defs = Definitions(
    assets=load_assets_from_modules(modules=[ldap]),
    resources={
        "io_manager_gcs_avro": get_io_manager_gcs_avro(CODE_LOCATION),
        "ldap": LDAP_RESOURCE,
    },
)

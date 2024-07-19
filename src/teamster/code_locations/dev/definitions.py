import warnings

from dagster import ExperimentalWarning

warnings.filterwarnings("ignore", category=ExperimentalWarning)

# trunk-ignore-begin(ruff/E402)
from dagster import Definitions, load_assets_from_modules

from teamster.code_locations.kipptaf import (  # adp,; airbyte,; amplify,; couchdrop,; datagun,; deanslist,; fivetran,;  ldap,; performance_management,; powerschool,; schoolmint,; smartrecruiters,; tableau; overgrad,; resources,; _google,
    CODE_LOCATION,
    _dbt,
)
from teamster.libraries.core.resources import (  # BIGQUERY_RESOURCE,; SSH_COUCHDROP,
    GCS_RESOURCE,
    get_dbt_cli_resource,
    get_io_manager_gcs_avro,
    get_io_manager_gcs_file,
    get_io_manager_gcs_pickle,
)

# trunk-ignore-end(ruff/E402)

defs = Definitions(
    assets=load_assets_from_modules(
        modules=[
            _dbt,
            # _google,
            # adp,
            # airbyte,
            # amplify,
            # datagun,
            # deanslist,
            # fivetran,
            # ldap,
            # performance_management,
            # powerschool,
            # schoolmint,
            # smartrecruiters,
            # tableau,
            # overgrad,
        ]
    ),
    # schedules=[
    #     *_dbt.schedules,
    #     *_google.schedules,
    #     *adp.schedules,
    #     *airbyte.schedules,
    #     *amplify.schedules,
    #     *datagun.schedules,
    #     *fivetran.schedules,
    #     *ldap.schedules,
    #     *schoolmint.schedules,
    #     *smartrecruiters.schedules,
    #     *tableau.schedules,
    # ],
    # sensors=[
    #     *adp.sensors,
    #     *airbyte.sensors,
    #     *couchdrop.sensors,
    #     *deanslist.sensors,
    #     *fivetran.sensors,
    #     *google.sensors,
    #     *tableau.sensors,
    # ],
    resources={
        "dbt_cli": get_dbt_cli_resource(CODE_LOCATION),
        "gcs": GCS_RESOURCE,
        "io_manager_gcs_avro": get_io_manager_gcs_avro(CODE_LOCATION),
        "io_manager_gcs_file": get_io_manager_gcs_file(CODE_LOCATION),
        "io_manager": get_io_manager_gcs_pickle(CODE_LOCATION),
        # "overgrad": resources.OVERGRAD_RESOURCE,
        # "adp_wfm": resources.ADP_WORKFORCE_MANAGER_RESOURCE,
        # "adp_wfn": resources.ADP_WORKFORCE_NOW_RESOURCE,
        # "airbyte": resources.AIRBYTE_CLOUD_RESOURCE,
        # "db_bigquery": BIGQUERY_RESOURCE,
        # "fivetran": resources.FIVETRAN_RESOURCE,
        # "google_directory": resources.GOOGLE_DIRECTORY_RESOURCE,
        # "google_drive": resources.GOOGLE_DRIVE_RESOURCE,
        # "google_forms": resources.GOOGLE_FORMS_RESOURCE,
        # "gsheets": resources.GOOGLE_SHEETS_RESOURCE,
        # "ldap": resources.LDAP_RESOURCE,
        # "mclass": resources.MCLASS_RESOURCE,
        # "ps_enrollment": resources.POWERSCHOOL_ENROLLMENT_RESOURCE,
        # "schoolmint_grow": resources.SCHOOLMINT_GROW_RESOURCE,
        # "smartrecruiters": resources.SMARTRECRUITERS_RESOURCE,
        # "ssh_adp_workforce_now": resources.SSH_RESOURCE_ADP_WORKFORCE_NOW,
        # "ssh_clever": resources.SSH_RESOURCE_CLEVER,
        # "ssh_couchdrop": SSH_COUCHDROP,
        # "ssh_coupa": resources.SSH_RESOURCE_COUPA,
        # "ssh_deanslist": resources.SSH_RESOURCE_DEANSLIST,
        # "ssh_egencia": resources.SSH_RESOURCE_EGENCIA,
        # "ssh_idauto": resources.SSH_RESOURCE_IDAUTO,
        # "ssh_illuminate": resources.SSH_RESOURCE_ILLUMINATE,
        # "ssh_littlesis": resources.SSH_RESOURCE_LITTLESIS,
        # "tableau": resources.TABLEAU_SERVER_RESOURCE,
    },
)

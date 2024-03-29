from dagster import Definitions, load_assets_from_modules
from dagster_k8s import k8s_job_executor

from teamster.core.resources import (
    BIGQUERY_RESOURCE,
    DB_POWERSCHOOL,
    DEANSLIST_RESOURCE,
    GCS_RESOURCE,
    SSH_COUCHDROP,
    SSH_EDPLAN,
    SSH_TITAN,
    get_dbt_cli_resource,
    get_io_manager_gcs_avro,
    get_io_manager_gcs_file,
    get_io_manager_gcs_pickle,
    get_ssh_resource_powerschool,
)

from . import (
    CODE_LOCATION,
    datagun,
    dbt,
    deanslist,
    edplan,
    pearson,
    powerschool,
    titan,
)

CODE_LOCATION_UPPER = CODE_LOCATION.upper()

defs = Definitions(
    executor=k8s_job_executor,
    assets=load_assets_from_modules(
        modules=[
            datagun,
            dbt,
            deanslist,
            edplan,
            pearson,
            powerschool,
            titan,
        ]
    ),
    schedules=[
        *datagun.schedules,
        *dbt.schedules,
        *deanslist.schedules,
        *powerschool.schedules,
    ],
    sensors=[
        *edplan.sensors,
        *powerschool.sensors,
        *titan.sensors,
    ],
    resources={
        "gcs": GCS_RESOURCE,
        "deanslist": DEANSLIST_RESOURCE,
        "db_bigquery": BIGQUERY_RESOURCE,
        "db_powerschool": DB_POWERSCHOOL,
        "ssh_couchdrop": SSH_COUCHDROP,
        "ssh_edplan": SSH_EDPLAN,
        "ssh_titan": SSH_TITAN,
        "io_manager": get_io_manager_gcs_pickle(CODE_LOCATION),
        "io_manager_gcs_avro": get_io_manager_gcs_avro(CODE_LOCATION),
        "io_manager_gcs_file": get_io_manager_gcs_file(CODE_LOCATION),
        "dbt_cli": get_dbt_cli_resource(CODE_LOCATION),
        "ssh_powerschool": get_ssh_resource_powerschool(
            remote_host="pskcna.kippnj.org"
        ),
    },
)

from dagster import Definitions, load_assets_from_modules
from dagster_k8s import k8s_job_executor

from teamster.code_locations.kippcamden import (
    CODE_LOCATION,
    _dbt,
    couchdrop,
    datagun,
    deanslist,
    edplan,
    pearson,
    powerschool,
    titan,
)
from teamster.core.resources import (
    BIGQUERY_RESOURCE,
    DB_POWERSCHOOL,
    DEANSLIST_RESOURCE,
    GCS_RESOURCE,
    SSH_COUCHDROP,
    SSH_EDPLAN,
    SSH_POWERSCHOOL,
    SSH_TITAN,
    get_dbt_cli_resource,
    get_io_manager_gcs_avro,
    get_io_manager_gcs_file,
    get_io_manager_gcs_pickle,
)

defs = Definitions(
    executor=k8s_job_executor,
    assets=load_assets_from_modules(
        modules=[
            _dbt,
            datagun,
            deanslist,
            edplan,
            pearson,
            powerschool,
            titan,
        ]
    ),
    schedules=[
        *_dbt.schedules,
        *datagun.schedules,
        *deanslist.schedules,
        *powerschool.schedules,
    ],
    sensors=[
        *couchdrop.sensors,
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
        "ssh_powerschool": SSH_POWERSCHOOL,
        "ssh_titan": SSH_TITAN,
        "io_manager": get_io_manager_gcs_pickle(CODE_LOCATION),
        "io_manager_gcs_avro": get_io_manager_gcs_avro(CODE_LOCATION),
        "io_manager_gcs_file": get_io_manager_gcs_file(CODE_LOCATION),
        "dbt_cli": get_dbt_cli_resource(CODE_LOCATION),
    },
)

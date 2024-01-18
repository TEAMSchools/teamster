from dagster import Definitions, load_assets_from_modules
from dagster_k8s import k8s_job_executor

from teamster.core.resources import (
    BIGQUERY_RESOURCE,
    DEANSLIST_RESOURCE,
    GCS_RESOURCE,
    SSH_COUCHDROP,
    SSH_IREADY,
    get_dbt_cli_resource,
    get_io_manager_gcs_avro,
    get_io_manager_gcs_file,
    get_io_manager_gcs_pickle,
    get_oracle_resource_powerschool,
    get_ssh_resource_edplan,
    get_ssh_resource_powerschool,
    get_ssh_resource_renlearn,
    get_ssh_resource_titan,
)

from . import (
    CODE_LOCATION,
    datagun,
    dbt,
    deanslist,
    edplan,
    iready,
    pearson,
    powerschool,
    renlearn,
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
            iready,
            pearson,
            powerschool,
            renlearn,
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
        *iready.sensors,
        *powerschool.sensors,
        *renlearn.sensors,
        *titan.sensors,
    ],
    resources={
        "gcs": GCS_RESOURCE,
        "db_bigquery": BIGQUERY_RESOURCE,
        "deanslist": DEANSLIST_RESOURCE,
        "ssh_couchdrop": SSH_COUCHDROP,
        "ssh_iready": SSH_IREADY,
        "io_manager": get_io_manager_gcs_pickle(CODE_LOCATION),
        "io_manager_gcs_avro": get_io_manager_gcs_avro(CODE_LOCATION),
        "io_manager_gcs_file": get_io_manager_gcs_file(CODE_LOCATION),
        "dbt_cli": get_dbt_cli_resource(CODE_LOCATION),
        "db_powerschool": get_oracle_resource_powerschool(CODE_LOCATION_UPPER),
        "ssh_edplan": get_ssh_resource_edplan(CODE_LOCATION_UPPER),
        "ssh_powerschool": get_ssh_resource_powerschool(
            remote_host="psteam.kippnj.org", code_location=CODE_LOCATION_UPPER
        ),
        "ssh_renlearn": get_ssh_resource_renlearn("KIPPNJ"),
        "ssh_titan": get_ssh_resource_titan(CODE_LOCATION_UPPER),
    },
)

from dagster import (
    AssetSelection,
    AutomationConditionSensorDefinition,
    Definitions,
    load_assets_from_modules,
)
from dagster_k8s import k8s_job_executor

from teamster.code_locations.kippnewark import (
    CODE_LOCATION,
    _dbt,
    couchdrop,
    datagun,
    deanslist,
    edplan,
    iready,
    overgrad,
    pearson,
    powerschool,
    renlearn,
    titan,
)
from teamster.core.resources import (
    BIGQUERY_RESOURCE,
    DB_POWERSCHOOL,
    DEANSLIST_RESOURCE,
    GCS_RESOURCE,
    OVERGRAD_RESOURCE,
    SSH_COUCHDROP,
    SSH_EDPLAN,
    SSH_IREADY,
    SSH_POWERSCHOOL,
    SSH_RENLEARN,
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
            iready,
            overgrad,
            pearson,
            powerschool,
            renlearn,
            titan,
        ]
    ),
    schedules=[
        *datagun.schedules,
        *deanslist.schedules,
        *overgrad.schedules,
        *powerschool.schedules,
    ],
    sensors=[
        *couchdrop.sensors,
        *edplan.sensors,
        *iready.sensors,
        *powerschool.sensors,
        *renlearn.sensors,
        *titan.sensors,
        AutomationConditionSensorDefinition(
            name=f"{CODE_LOCATION}__automation_condition_sensor",
            asset_selection=AssetSelection.all(),
        ),
    ],
    resources={
        "db_bigquery": BIGQUERY_RESOURCE,
        "db_powerschool": DB_POWERSCHOOL,
        "dbt_cli": get_dbt_cli_resource(_dbt.dbt_project),
        "deanslist": DEANSLIST_RESOURCE,
        "gcs": GCS_RESOURCE,
        "io_manager_gcs_avro": get_io_manager_gcs_avro(CODE_LOCATION),
        "io_manager_gcs_file": get_io_manager_gcs_file(CODE_LOCATION),
        "io_manager": get_io_manager_gcs_pickle(CODE_LOCATION),
        "overgrad": OVERGRAD_RESOURCE,
        "ssh_couchdrop": SSH_COUCHDROP,
        "ssh_edplan": SSH_EDPLAN,
        "ssh_iready": SSH_IREADY,
        "ssh_powerschool": SSH_POWERSCHOOL,
        "ssh_renlearn": SSH_RENLEARN,
        "ssh_titan": SSH_TITAN,
    },
)

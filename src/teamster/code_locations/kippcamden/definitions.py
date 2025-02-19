from dagster import (
    AssetSelection,
    AutomationConditionSensorDefinition,
    Definitions,
    load_assets_from_modules,
)
from dagster_k8s import k8s_job_executor

from teamster.code_locations.kippcamden import (
    CODE_LOCATION,
    DBT_PROJECT,
    _dbt,
    couchdrop,
    deanslist,
    edplan,
    extracts,
    overgrad,
    pearson,
    powerschool,
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
    SSH_TITAN,
    get_dbt_cli_resource,
    get_io_manager_gcs_avro,
    get_io_manager_gcs_file,
    get_io_manager_gcs_pickle,
    get_powerschool_ssh_resource,
)

defs = Definitions(
    executor=k8s_job_executor,
    assets=load_assets_from_modules(
        modules=[
            _dbt,
            extracts,
            deanslist,
            edplan,
            overgrad,
            pearson,
            powerschool,
            titan,
        ]
    ),
    schedules=[
        *extracts.schedules,
        *deanslist.schedules,
        *overgrad.schedules,
        *powerschool.schedules,
    ],
    sensors=[
        *couchdrop.sensors,
        *edplan.sensors,
        *powerschool.sensors,
        *titan.sensors,
        AutomationConditionSensorDefinition(
            name=f"{CODE_LOCATION}__automation_condition_sensor",
            target=AssetSelection.all(),
        ),
    ],
    resources={
        "db_bigquery": BIGQUERY_RESOURCE,
        "db_powerschool": DB_POWERSCHOOL,
        "dbt_cli": get_dbt_cli_resource(DBT_PROJECT),
        "deanslist": DEANSLIST_RESOURCE,
        "gcs": GCS_RESOURCE,
        "io_manager_gcs_avro": get_io_manager_gcs_avro(CODE_LOCATION),
        "io_manager_gcs_file": get_io_manager_gcs_file(CODE_LOCATION),
        "io_manager": get_io_manager_gcs_pickle(CODE_LOCATION),
        "overgrad": OVERGRAD_RESOURCE,
        "ssh_couchdrop": SSH_COUCHDROP,
        "ssh_edplan": SSH_EDPLAN,
        "ssh_powerschool": get_powerschool_ssh_resource(),
        "ssh_titan": SSH_TITAN,
    },
)

from dagster import (
    AssetSelection,
    AutomationConditionSensorDefinition,
    Definitions,
    load_assets_from_modules,
)
from dagster_k8s import k8s_job_executor

from teamster.code_locations.kippmiami import (
    CODE_LOCATION,
    DBT_PROJECT,
    _dbt,
    couchdrop,
    datagun,
    deanslist,
    fldoe,
    iready,
    powerschool,
    renlearn,
)
from teamster.core.resources import (
    BIGQUERY_RESOURCE,
    DB_POWERSCHOOL,
    DEANSLIST_RESOURCE,
    GCS_RESOURCE,
    SSH_COUCHDROP,
    SSH_IREADY,
    SSH_POWERSCHOOL,
    SSH_RENLEARN,
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
            fldoe,
            iready,
            powerschool,
            renlearn,
        ]
    ),
    schedules=[
        *datagun.schedules,
        *deanslist.schedules,
        *powerschool.schedules,
    ],
    sensors=[
        *couchdrop.sensors,
        *iready.sensors,
        *powerschool.sensors,
        *renlearn.sensors,
        AutomationConditionSensorDefinition(
            name=f"{CODE_LOCATION}__automation_condition_sensor",
            asset_selection=AssetSelection.all(),
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
        "ssh_couchdrop": SSH_COUCHDROP,
        "ssh_iready": SSH_IREADY,
        "ssh_powerschool": SSH_POWERSCHOOL,
        "ssh_renlearn": SSH_RENLEARN,
    },
)

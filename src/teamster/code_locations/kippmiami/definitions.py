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
    couchdrop,
    dbt,
    deanslist,
    dlt,
    extracts,
    finalsite,
    fldoe,
    iready,
    renlearn,
)
from teamster.code_locations.kippmiami.resources import FINALSITE_RESOURCE, SSH_FOCUS
from teamster.core.resources import (
    BIGQUERY_RESOURCE,
    DEANSLIST_RESOURCE,
    DLT_RESOURCE,
    GCS_RESOURCE,
    GOOGLE_DRIVE_RESOURCE,
    SSH_COUCHDROP,
    SSH_IREADY,
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
            dbt,
            dlt,
            extracts,
            deanslist,
            finalsite,
            fldoe,
            iready,
            renlearn,
        ]
    ),
    schedules=[
        *dlt.schedules,
        *extracts.schedules,
        *deanslist.schedules,
        *finalsite.schedules,
    ],
    sensors=[
        *couchdrop.sensors,
        *iready.sensors,
        *renlearn.sensors,
        AutomationConditionSensorDefinition(
            name=f"{CODE_LOCATION}__automation_condition_sensor",
            target=AssetSelection.all(),
        ),
    ],
    resources={
        "db_bigquery": BIGQUERY_RESOURCE,
        "dbt_cli": get_dbt_cli_resource(DBT_PROJECT),
        "deanslist": DEANSLIST_RESOURCE,
        "dlt": DLT_RESOURCE,
        "finalsite": FINALSITE_RESOURCE,
        "gcs": GCS_RESOURCE,
        "google_drive": GOOGLE_DRIVE_RESOURCE,
        "io_manager_gcs_avro": get_io_manager_gcs_avro(CODE_LOCATION),
        "io_manager_gcs_file": get_io_manager_gcs_file(CODE_LOCATION),
        "io_manager": get_io_manager_gcs_pickle(CODE_LOCATION),
        "ssh_couchdrop": SSH_COUCHDROP,
        "ssh_focus": SSH_FOCUS,
        "ssh_iready": SSH_IREADY,
        "ssh_renlearn": SSH_RENLEARN,
    },
)

from dagster import (
    AssetSelection,
    AutomationConditionSensorDefinition,
    Definitions,
    load_assets_from_modules,
)
from dagster_k8s import k8s_job_executor

from teamster.code_locations.kipppaterson import (
    CODE_LOCATION,
    DBT_PROJECT,
    amplify,
    couchdrop,
    dbt,
    deanslist,
    finalsite,
    pearson,
    powerschool,
)
from teamster.core.resources import (
    DEANSLIST_RESOURCE,
    GCS_RESOURCE,
    GOOGLE_DRIVE_RESOURCE,
    SSH_COUCHDROP,
    SSH_RESOURCE_AMPLIFY,
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
            amplify,
            deanslist,
            finalsite,
            pearson,
            powerschool,
        ]
    ),
    schedules=[
        *deanslist.schedules,
    ],
    sensors=[
        *amplify.sensors,
        *couchdrop.sensors,
        AutomationConditionSensorDefinition(
            name=f"{CODE_LOCATION}__automation_condition_sensor",
            target=AssetSelection.all(),
        ),
    ],
    resources={
        "dbt_cli": get_dbt_cli_resource(DBT_PROJECT),
        "deanslist": DEANSLIST_RESOURCE,
        "gcs": GCS_RESOURCE,
        "google_drive": GOOGLE_DRIVE_RESOURCE,
        "io_manager_gcs_avro": get_io_manager_gcs_avro(CODE_LOCATION),
        "io_manager_gcs_file": get_io_manager_gcs_file(CODE_LOCATION),
        "io_manager": get_io_manager_gcs_pickle(CODE_LOCATION),
        "ssh_amplify": SSH_RESOURCE_AMPLIFY,
        "ssh_couchdrop": SSH_COUCHDROP,
    },
)

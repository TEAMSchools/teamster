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
    _dbt,
    amplify,
    couchdrop,
    finalsite,
    pearson,
    powerschool,
)
from teamster.core.resources import (
    GCS_RESOURCE,
    GOOGLE_DRIVE_RESOURCE,
    SSH_COUCHDROP,
    SSH_RESOURCE_AMPLIFY,
    get_dbt_cli_resource,
    get_io_manager_gcs_avro,
    get_io_manager_gcs_pickle,
)

defs = Definitions(
    executor=k8s_job_executor,
    assets=load_assets_from_modules(
        modules=[
            _dbt,
            amplify,
            finalsite,
            pearson,
            powerschool,
        ]
    ),
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
        "gcs": GCS_RESOURCE,
        "google_drive": GOOGLE_DRIVE_RESOURCE,
        "io_manager_gcs_avro": get_io_manager_gcs_avro(CODE_LOCATION),
        "io_manager": get_io_manager_gcs_pickle(CODE_LOCATION),
        "ssh_amplify": SSH_RESOURCE_AMPLIFY,
        "ssh_couchdrop": SSH_COUCHDROP,
    },
)

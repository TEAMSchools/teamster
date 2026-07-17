from dagster import (
    AssetSelection,
    AutomationConditionSensorDefinition,
    Definitions,
    load_assets_from_modules,
)
from dagster_dlt import DagsterDltResource
from dagster_k8s import k8s_job_executor

from teamster.code_locations.kippcamden import (
    CODE_LOCATION,
    DBT_PROJECT,
    couchdrop,
    dbt,
    deanslist,
    edplan,
    extracts,
    finalsite,
    freshness,
    overgrad,
    pearson,
    powerschool,
    titan,
)
from teamster.code_locations.kippcamden.resources import FINALSITE_RESOURCE
from teamster.core.freshness import apply_freshness_policies
from teamster.core.resources import (
    BIGQUERY_RESOURCE,
    DEANSLIST_RESOURCE,
    GCS_RESOURCE,
    GOOGLE_DRIVE_RESOURCE,
    OVERGRAD_RESOURCE,
    SSH_COUCHDROP,
    SSH_EDPLAN,
    SSH_TITAN,
    get_dbt_cli_resource,
    get_io_manager_gcs_avro,
    get_io_manager_gcs_file,
    get_io_manager_gcs_pickle,
    get_powerschool_oracle_resource,
    get_powerschool_ssh_resource,
)

defs = Definitions(
    executor=k8s_job_executor,
    assets=apply_freshness_policies(
        load_assets_from_modules(
            modules=[
                dbt,
                extracts,
                deanslist,
                edplan,
                finalsite,
                overgrad,
                pearson,
                powerschool,
                titan,
            ]
        ),
        policies=freshness.policies,
    ),
    schedules=[
        *extracts.schedules,
        *deanslist.schedules,
        *finalsite.schedules,
        *overgrad.schedules,
        *powerschool.schedules,
    ],
    sensors=[
        *couchdrop.sensors,
        *edplan.sensors,
        *titan.sensors,
        AutomationConditionSensorDefinition(
            name=f"{CODE_LOCATION}__automation_condition_sensor",
            target=AssetSelection.all(),
        ),
    ],
    resources={
        "db_bigquery": BIGQUERY_RESOURCE,
        "db_powerschool": get_powerschool_oracle_resource(),
        "dbt_cli": get_dbt_cli_resource(DBT_PROJECT),
        "deanslist": DEANSLIST_RESOURCE,
        "dlt": DagsterDltResource(),
        "finalsite": FINALSITE_RESOURCE,
        "gcs": GCS_RESOURCE,
        "google_drive": GOOGLE_DRIVE_RESOURCE,
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

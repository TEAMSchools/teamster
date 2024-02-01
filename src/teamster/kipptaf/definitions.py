from dagster import Definitions, load_assets_from_modules
from dagster_k8s import k8s_job_executor

from teamster.core.resources import (
    BIGQUERY_RESOURCE,
    GCS_RESOURCE,
    SSH_COUCHDROP,
    get_dbt_cli_resource,
    get_io_manager_gcs_avro,
    get_io_manager_gcs_file,
    get_io_manager_gcs_pickle,
)

from . import (
    CODE_LOCATION,
    achieve3k,
    airbyte,
    alchemer,
    amplify,
    datagun,
    dayforce,
    deanslist,
    fivetran,
    ldap,
    performance_management,
    resources,
    schoolmint,
    smartrecruiters,
    zendesk,
)
from .adp import payroll, workforce_manager, workforce_now
from .dbt import assets as dbt_assets
from .dbt.schedules import _all as dbt_schedules
from .google import directory, forms, sheets

defs = Definitions(
    executor=k8s_job_executor,
    assets=load_assets_from_modules(
        modules=[
            achieve3k,
            airbyte,
            alchemer,
            amplify,
            datagun,
            dayforce,
            dbt_assets,
            deanslist,
            directory,
            fivetran,
            forms,
            ldap,
            payroll,
            performance_management,
            schoolmint,
            sheets,
            smartrecruiters,
            workforce_manager,
            workforce_now,
            zendesk,
        ]
    ),
    schedules=[
        *airbyte.schedules,
        *amplify.schedules,
        *datagun.schedules,
        *dbt_schedules,
        *directory.schedules,
        *fivetran.schedules,
        *forms.schedules,
        *ldap.schedules,
        *schoolmint.schedules,
        *smartrecruiters.schedules,
        *workforce_manager.schedules,
        *workforce_now.schedules,
    ],
    sensors=[
        *achieve3k.sensors,
        *airbyte.sensors,
        *alchemer.sensors,
        *deanslist.sensors,
        *fivetran.sensors,
        *payroll.sensors,
        *sheets.sensors,
        *workforce_now.sensors,
    ],
    resources={
        # shared
        "gcs": GCS_RESOURCE,
        "db_bigquery": BIGQUERY_RESOURCE,
        "ssh_couchdrop": SSH_COUCHDROP,
        # regional
        "io_manager": get_io_manager_gcs_pickle(CODE_LOCATION),
        "io_manager_gcs_avro": get_io_manager_gcs_avro(CODE_LOCATION),
        "io_manager_gcs_file": get_io_manager_gcs_file(CODE_LOCATION),
        "dbt_cli": get_dbt_cli_resource(CODE_LOCATION),
        "adp_wfm": resources.ADP_WORKFORCE_MANAGER_RESOURCE,
        "adp_wfn": resources.ADP_WORKFORCE_NOW_RESOURCE,
        "airbyte": resources.AIRBYTE_CLOUD_RESOURCE,
        "alchemer": resources.ALCHEMER_RESOURCE,
        "fivetran": resources.FIVETRAN_RESOURCE,
        "google_directory": resources.GOOGLE_DIRECTORY_RESOURCE,
        "google_forms": resources.GOOGLE_FORMS_RESOURCE,
        "gsheets": resources.GOOGLE_SHEETS_RESOURCE,
        "ldap": resources.LDAP_RESOURCE,
        "mclass": resources.MCLASS_RESOURCE,
        "schoolmint_grow": resources.SCHOOLMINT_GROW_RESOURCE,
        "smartrecruiters": resources.SMARTRECRUITERS_RESOURCE,
        "zendesk": resources.ZENDESK_RESOURCE,
        # ssh
        "ssh_achieve3k": resources.SSH_RESOURCE_ACHIEVE3K,
        "ssh_adp_workforce_now": resources.SSH_RESOURCE_ADP_WORKFORCE_NOW,
        "ssh_blissbook": resources.SSH_RESOURCE_BLISSBOOK,
        "ssh_clever": resources.SSH_RESOURCE_CLEVER,
        "ssh_coupa": resources.SSH_RESOURCE_COUPA,
        "ssh_deanslist": resources.SSH_RESOURCE_DEANSLIST,
        "ssh_egencia": resources.SSH_RESOURCE_EGENCIA,
        "ssh_idauto": resources.SSH_RESOURCE_IDAUTO,
        "ssh_illuminate": resources.SSH_RESOURCE_ILLUMINATE,
        "ssh_littlesis": resources.SSH_RESOURCE_LITTLESIS,
    },
)

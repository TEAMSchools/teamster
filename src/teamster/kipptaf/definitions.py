from dagster import (
    Definitions,
    ScheduleDefinition,
    config_from_files,
    load_assets_from_modules,
)
from dagster._core.definitions.unresolved_asset_job_definition import (
    UnresolvedAssetJobDefinition,
)
from dagster_gcp.gcs import gcs_pickle_io_manager, gcs_resource
from dagster_k8s import k8s_job_executor

from teamster.core.resources.google import google_sheets
from teamster.core.resources.sqlalchemy import mssql
from teamster.core.resources.ssh import ssh_resource
from teamster.kipptaf.datagun import assets as local_datagun_assets
from teamster.kipptaf.datagun import jobs as local_datagun_jobs
from teamster.kipptaf.datagun import schedules as local_datagun_schedules

CODE_LOCATION = "kipptaf"

defs = Definitions(
    executor=k8s_job_executor,
    assets=load_assets_from_modules(
        modules=[local_datagun_assets], group_name="datagun"
    ),
    jobs=[
        obj
        for key, obj in vars(local_datagun_jobs).items()
        if isinstance(obj, UnresolvedAssetJobDefinition)
    ],
    schedules=[
        obj
        for key, obj in vars(local_datagun_schedules).items()
        if isinstance(obj, ScheduleDefinition)
    ],
    resources={
        "gcs": gcs_resource.configured(
            config_from_files(["src/teamster/core/resources/config/gcs.yaml"])
        ),
        "warehouse": mssql.configured(
            config_from_files(["src/teamster/core/resources/config/warehouse.yaml"])
        ),
        "sftp_pythonanywhere": ssh_resource.configured(
            config_from_files(
                ["src/teamster/core/resources/config/sftp_pythonanywhere.yaml"]
            )
        ),
        "io_manager": gcs_pickle_io_manager.configured(
            config_from_files(
                [f"src/teamster/{CODE_LOCATION}/resources/config/io.yaml"]
            )
        ),
        "gsheets": google_sheets.configured(
            config_from_files(
                [f"src/teamster/{CODE_LOCATION}/resources/config/gsheets.yaml"]
            )
        ),
        "sftp_blissbook": ssh_resource.configured(
            config_from_files(
                [f"src/teamster/{CODE_LOCATION}/resources/config/sftp_blissbook.yaml"]
            )
        ),
        "sftp_clever": ssh_resource.configured(
            config_from_files(
                [f"src/teamster/{CODE_LOCATION}/resources/config/sftp_clever.yaml"]
            )
        ),
        "sftp_coupa": ssh_resource.configured(
            config_from_files(
                [f"src/teamster/{CODE_LOCATION}/resources/config/sftp_coupa.yaml"]
            )
        ),
        "sftp_deanslist": ssh_resource.configured(
            config_from_files(
                [f"src/teamster/{CODE_LOCATION}/resources/config/sftp_deanslist.yaml"]
            )
        ),
        "sftp_egencia": ssh_resource.configured(
            config_from_files(
                [f"src/teamster/{CODE_LOCATION}/resources/config/sftp_egencia.yaml"]
            )
        ),
        "sftp_illuminate": ssh_resource.configured(
            config_from_files(
                [f"src/teamster/{CODE_LOCATION}/resources/config/sftp_illuminate.yaml"]
            )
        ),
        "sftp_kipptaf": ssh_resource.configured(
            config_from_files(
                [f"src/teamster/{CODE_LOCATION}/resources/config/sftp_kipptaf.yaml"]
            )
        ),
        "sftp_littlesis": ssh_resource.configured(
            config_from_files(
                [f"src/teamster/{CODE_LOCATION}/resources/config/sftp_littlesis.yaml"]
            )
        ),
        "sftp_razkids": ssh_resource.configured(
            config_from_files(
                [f"src/teamster/{CODE_LOCATION}/resources/config/sftp_razkids.yaml"]
            )
        ),
        "sftp_read180": ssh_resource.configured(
            config_from_files(
                [f"src/teamster/{CODE_LOCATION}/resources/config/sftp_read180.yaml"]
            )
        ),
    },
)

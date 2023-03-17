from dagster import Definitions, config_from_files, load_assets_from_modules
from dagster_gcp.gcs import gcs_pickle_io_manager, gcs_resource
from dagster_k8s import k8s_job_executor
from dagster_ssh import ssh_resource

from teamster.core.resources.google import google_sheets
from teamster.core.resources.sqlalchemy import mssql

from . import CODE_LOCATION, datagun

defs = Definitions(
    executor=k8s_job_executor,
    assets=load_assets_from_modules(modules=[datagun.assets], group_name="datagun"),
    jobs=datagun.jobs.__all__,
    schedules=datagun.schedules.__all__,
    resources={
        "gcs": gcs_resource.configured(
            config_from_files(["src/teamster/core/config/resources/gcs.yaml"])
        ),
        "warehouse": mssql.configured(
            config_from_files(["src/teamster/core/config/resources/warehouse.yaml"])
        ),
        "sftp_pythonanywhere": ssh_resource.configured(
            config_from_files(
                ["src/teamster/core/config/resources/sftp_pythonanywhere.yaml"]
            )
        ),
        "io_manager": gcs_pickle_io_manager.configured(
            config_from_files(
                [f"src/teamster/{CODE_LOCATION}/config/resources/io.yaml"]
            )
        ),
        "gsheets": google_sheets.configured(
            config_from_files(["src/teamster/core/config/resources/gsheets.yaml"])
        ),
        "sftp_blissbook": ssh_resource.configured(
            config_from_files(
                [f"src/teamster/{CODE_LOCATION}/config/resources/sftp_blissbook.yaml"]
            )
        ),
        "sftp_clever": ssh_resource.configured(
            config_from_files(
                [f"src/teamster/{CODE_LOCATION}/config/resources/sftp_clever.yaml"]
            )
        ),
        "sftp_coupa": ssh_resource.configured(
            config_from_files(
                [f"src/teamster/{CODE_LOCATION}/config/resources/sftp_coupa.yaml"]
            )
        ),
        "sftp_deanslist": ssh_resource.configured(
            config_from_files(
                [f"src/teamster/{CODE_LOCATION}/config/resources/sftp_deanslist.yaml"]
            )
        ),
        "sftp_egencia": ssh_resource.configured(
            config_from_files(
                [f"src/teamster/{CODE_LOCATION}/config/resources/sftp_egencia.yaml"]
            )
        ),
        "sftp_illuminate": ssh_resource.configured(
            config_from_files(
                [f"src/teamster/{CODE_LOCATION}/config/resources/sftp_illuminate.yaml"]
            )
        ),
        "sftp_kipptaf": ssh_resource.configured(
            config_from_files(
                [f"src/teamster/{CODE_LOCATION}/config/resources/sftp_kipptaf.yaml"]
            )
        ),
        "sftp_littlesis": ssh_resource.configured(
            config_from_files(
                [f"src/teamster/{CODE_LOCATION}/config/resources/sftp_littlesis.yaml"]
            )
        ),
        "sftp_razkids": ssh_resource.configured(
            config_from_files(
                [f"src/teamster/{CODE_LOCATION}/config/resources/sftp_razkids.yaml"]
            )
        ),
        "sftp_read180": ssh_resource.configured(
            config_from_files(
                [f"src/teamster/{CODE_LOCATION}/config/resources/sftp_read180.yaml"]
            )
        ),
    },
)

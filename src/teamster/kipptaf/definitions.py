from dagster import Definitions, config_from_files, load_assets_from_modules
from dagster_gcp.gcs import gcs_pickle_io_manager, gcs_resource
from dagster_k8s import k8s_job_executor

from teamster.core.resources.google import google_sheets
from teamster.core.resources.sqlalchemy import mssql
from teamster.core.resources.ssh import ssh_resource
from teamster.kipptaf import CODE_LOCATION, datagun

defs = Definitions(
    executor=k8s_job_executor,
    assets=load_assets_from_modules(modules=[datagun.assets], group_name="datagun"),
    jobs=datagun.jobs.__all__,
    schedules=datagun.schedules.__all__,
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
            config_from_files(["src/teamster/core/resources/config/gsheets.yaml"])
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

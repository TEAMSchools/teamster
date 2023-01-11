from dagster import Definitions, config_from_files, load_assets_from_modules
from dagster_gcp.gcs import gcs_pickle_io_manager, gcs_resource

from teamster.core.resources.google import google_sheets
from teamster.core.resources.sqlalchemy import mssql
from teamster.core.resources.ssh import ssh_resource
from teamster.kipptaf.datagun import assets as local_datagun_assets

datagun_assets = load_assets_from_modules(
    modules=[local_datagun_assets], group_name="datagun"
)

defs = Definitions(
    assets=datagun_assets,
    resources={
        "io_manager": gcs_pickle_io_manager.configured(
            config_from_files(["src/teamster/core/resources/config/io.yaml"])
        ),
        "gcs": gcs_resource.configured(
            config_from_files(["src/teamster/core/resources/config/gcs.yaml"])
        ),
        "warehouse": mssql.configured(
            config_from_files(["src/teamster/core/datagun/config/warehouse.yaml"])
        ),
        "gsheet": google_sheets.configured(
            config_from_files(["src/teamster/kipptaf/datagun/config/gsheet.yaml"])
        ),
        "sftp_pythonanywhere": ssh_resource.configured(
            config_from_files(
                ["src/teamster/core/datagun/config/sftp_pythonanywhere.yaml"]
            )
        ),
        "sftp_blissbook": ssh_resource.configured(
            config_from_files(
                ["src/teamster/kipptaf/datagun/config/sftp_blissbook.yaml"]
            )
        ),
        "sftp_clever": ssh_resource.configured(
            config_from_files(["src/teamster/kipptaf/datagun/config/sftp_clever.yaml"])
        ),
        "sftp_coupa": ssh_resource.configured(
            config_from_files(["src/teamster/kipptaf/datagun/config/sftp_coupa.yaml"])
        ),
        "sftp_deanslist": ssh_resource.configured(
            config_from_files(
                ["src/teamster/kipptaf/datagun/config/sftp_deanslist.yaml"]
            )
        ),
        "sftp_egencia": ssh_resource.configured(
            config_from_files(["src/teamster/kipptaf/datagun/config/sftp_egencia.yaml"])
        ),
        "sftp_illuminate": ssh_resource.configured(
            config_from_files(
                ["src/teamster/kipptaf/datagun/config/sftp_illuminate.yaml"]
            )
        ),
        "sftp_kipptaf": ssh_resource.configured(
            config_from_files(["src/teamster/kipptaf/datagun/config/sftp_kipptaf.yaml"])
        ),
        "sftp_littlesis": ssh_resource.configured(
            config_from_files(
                ["src/teamster/kipptaf/datagun/config/sftp_littlesis.yaml"]
            )
        ),
        "sftp_razkids": ssh_resource.configured(
            config_from_files(["src/teamster/kipptaf/datagun/config/sftp_razkids.yaml"])
        ),
        "sftp_read180": ssh_resource.configured(
            config_from_files(["src/teamster/kipptaf/datagun/config/sftp_read180.yaml"])
        ),
    },
)

from dagster import Definitions, config_from_files, load_assets_from_modules
from dagster_gcp.gcs import gcs_pickle_io_manager, gcs_resource

from teamster.core.resources.google import google_sheets
from teamster.core.resources.sqlalchemy import mssql
from teamster.kipptaf.datagun import assets as local_datagun_assets

datagun_assets = load_assets_from_modules(
    modules=[local_datagun_assets], group_name="datagun"
)

defs = Definitions(
    assets=datagun_assets,
    resources={
        "warehouse": mssql.configured(
            config_from_files(["src/teamster/core/datagun/config/warehouse.yaml"])
        ),
        "gsheet": google_sheets.configured(
            config_from_files(["src/teamster/kipptaf/datagun/config/gsheet.yaml"])
        ),
        "io_manager": gcs_pickle_io_manager.configured(
            config_from_files(["src/teamster/core/resources/config/io.yaml"])
        ),
        "gcs": gcs_resource.configured(
            config_from_files(["src/teamster/core/resources/config/gcs.yaml"])
        ),
    },
)

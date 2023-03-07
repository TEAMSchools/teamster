from dagster import Definitions, config_from_files, load_assets_from_modules
from dagster_dbt import dbt_cli_resource
from dagster_gcp import bigquery_resource, gcs_resource
from dagster_gcp.gcs import gcs_pickle_io_manager
from dagster_k8s import k8s_job_executor
from dagster_ssh import ssh_resource

from teamster.core.resources.deanslist import deanslist_resource
from teamster.core.resources.google import (
    gcs_avro_io_manager,
    gcs_filepath_io_manager,
    google_sheets,
)
from teamster.core.resources.sqlalchemy import mssql, oracle

from . import CODE_LOCATION, datagun, dbt, deanslist, powerschool

defs = Definitions(
    executor=k8s_job_executor,
    assets=(
        load_assets_from_modules(
            modules=[powerschool.db.assets], group_name="powerschool"
        )
        + load_assets_from_modules(modules=[datagun.assets], group_name="datagun")
        + load_assets_from_modules(modules=[deanslist.assets], group_name="deanslist")
        + load_assets_from_modules(modules=[dbt.assets])
    ),
    jobs=datagun.jobs.__all__ + deanslist.jobs.__all__,
    resources={
        "dbt": dbt_cli_resource.configured(
            {
                "project-dir": f"teamster-dbt/{CODE_LOCATION}",
                "profiles-dir": f"teamster-dbt/{CODE_LOCATION}",
            }
        ),
        "warehouse_bq": bigquery_resource.configured(
            config_from_files(["src/teamster/core/resources/config/gcs.yaml"])
        ),
        "sftp_test": ssh_resource.configured(
            config_from_files(
                ["src/teamster/core/resources/config/sftp_pythonanywhere.yaml"]
            )
        ),
        "gcs": gcs_resource.configured(
            config_from_files(["src/teamster/core/resources/config/gcs.yaml"])
        ),
        "warehouse": mssql.configured(
            config_from_files(["src/teamster/core/resources/config/warehouse.yaml"])
        ),
        "ps_db": oracle.configured(
            config_from_files(
                ["src/teamster/core/resources/config/db_powerschool.yaml"]
            )
        ),
        "ps_ssh": ssh_resource.configured(
            config_from_files(
                ["src/teamster/core/resources/config/ssh_powerschool.yaml"]
            )
        ),
        "gcs_fp_io": gcs_filepath_io_manager.configured(
            config_from_files(
                [f"src/teamster/{CODE_LOCATION}/resources/config/io.yaml"]
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
        "deanslist": deanslist_resource.configured(
            config_from_files(
                [
                    "src/teamster/core/resources/config/deanslist.yaml",
                    f"src/teamster/{CODE_LOCATION}/resources/config/deanslist.yaml",
                ]
            )
        ),
        "gcs_avro_io": gcs_avro_io_manager.configured(
            config_from_files(
                [f"src/teamster/{CODE_LOCATION}/resources/config/io.yaml"]
            )
        ),
    },
)

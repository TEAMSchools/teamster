from dagster import (
    AssetSelection,
    Definitions,
    build_asset_reconciliation_sensor,
    config_from_files,
    load_assets_from_modules,
)
from dagster_gcp.gcs import gcs_pickle_io_manager, gcs_resource
from dagster_k8s import k8s_job_executor

from teamster.core.resources.google import gcs_filename_io_manager
from teamster.core.resources.sqlalchemy import mssql, oracle
from teamster.core.resources.ssh import ssh_resource

from . import CODE_LOCATION, datagun, powerschool

defs = Definitions(
    executor=k8s_job_executor,
    assets=(
        load_assets_from_modules(modules=[powerschool.assets], group_name="powerschool")
        + load_assets_from_modules(modules=[datagun.assets], group_name="datagun")
    ),
    jobs=datagun.jobs.__all__ + powerschool.jobs.__all__,
    schedules=datagun.schedules.__all__,  # + powerschool.schedules.__all__,
    sensors=[build_asset_reconciliation_sensor(asset_selection=AssetSelection.all())],
    resources={
        "io_manager": gcs_pickle_io_manager.configured(
            config_from_files(
                [f"src/teamster/{CODE_LOCATION}/resources/config/io.yaml"]
            )
        ),
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
        "sftp_cpn": ssh_resource.configured(
            config_from_files(
                [f"src/teamster/{CODE_LOCATION}/resources/config/sftp_cpn.yaml"]
            )
        ),
        "ps_io": gcs_filename_io_manager.configured(
            config_from_files(
                [f"src/teamster/{CODE_LOCATION}/resources/config/io.yaml"]
            )
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
    },
)

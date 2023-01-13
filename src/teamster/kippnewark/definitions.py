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

from teamster.core.resources.sqlalchemy import mssql, oracle
from teamster.core.resources.ssh import ssh_resource
from teamster.kippnewark.datagun import assets as local_datagun_assets
from teamster.kippnewark.datagun import jobs as local_datagun_jobs
from teamster.kippnewark.datagun import schedules as local_datagun_schedules
from teamster.kippnewark.powerschool.db import assets as ps_db_assets

CODE_LOCATION = "kippnewark"

defs = Definitions(
    executor=k8s_job_executor,
    assets=(
        load_assets_from_modules(
            modules=[ps_db_assets],
            group_name="powerschool",
            key_prefix=f"powerschool_{CODE_LOCATION}",
        )
        + load_assets_from_modules(modules=[local_datagun_assets], group_name="datagun")
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
        "sftp_nps": ssh_resource.configured(
            config_from_files(
                [f"src/teamster/{CODE_LOCATION}/resources/config/sftp_nps.yaml"]
            )
        ),
        "ps_db": oracle.configured(
            config_from_files(["src/teamster/core/powerschool/db/config/db.yaml"])
        ),
        "ps_ssh": ssh_resource.configured(
            config_from_files(["src/teamster/core/powerschool/db/config/ssh.yaml"])
        ),
    },
)

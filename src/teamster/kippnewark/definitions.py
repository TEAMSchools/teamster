from dagster import Definitions, config_from_files, load_assets_from_modules
from dagster_gcp.gcs import gcs_pickle_io_manager, gcs_resource
from dagster_k8s import k8s_job_executor

from teamster.core.powerschool.db import assets as core_ps_db_assets
from teamster.core.resources.sqlalchemy import mssql, oracle
from teamster.core.resources.ssh import ssh_resource
from teamster.kippnewark.datagun import assets as local_datagun_assets
from teamster.kippnewark.powerschool.db import assets as local_ps_db_assets

ps_db_assets = load_assets_from_modules(
    modules=[core_ps_db_assets, local_ps_db_assets],
    group_name="powerschool",
    key_prefix="powerschool",
)

datagun_assets = load_assets_from_modules(
    modules=[local_datagun_assets], group_name="datagun"
)

defs = Definitions(
    executor=k8s_job_executor,
    assets=ps_db_assets + datagun_assets,
    resources={
        "io_manager": gcs_pickle_io_manager.configured(
            config_from_files(["src/teamster/core/resources/config/io.yaml"])
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
                ["src/teamster/kippnewark/resources/config/sftp_nps.yaml"]
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

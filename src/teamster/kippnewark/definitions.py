from dagster import Definitions, config_from_files, load_assets_from_modules
from dagster_gcp.gcs import gcs_pickle_io_manager, gcs_resource

from teamster.core.powerschool.db import assets as core_ps_db_assets
from teamster.core.resources.sqlalchemy import oracle
from teamster.core.resources.ssh import ssh_resource
from teamster.kippnewark.powerschool.db import assets as local_ps_db_assets

defs = Definitions(
    # assets=core_ps_db_assets + local_ps_db_assets,
    assets=load_assets_from_modules(
        modules=[core_ps_db_assets, local_ps_db_assets], group_name="powerschool"
    ),
    resources={
        "ps_db": oracle.configured(
            config_from_files(["src/teamster/core/powerschool/db/config/db.yaml"])
        ),
        "ps_ssh": ssh_resource.configured(
            config_from_files(["src/teamster/core/powerschool/db/config/ssh.yaml"])
        ),
        "io_manager": gcs_pickle_io_manager.configured(
            config_from_files(["src/teamster/core/resources/config/io.yaml"])
        ),
        "gcs": gcs_resource.configured(
            config_from_files(["src/teamster/core/resources/config/gcs.yaml"])
        ),
    },
)

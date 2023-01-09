from dagster import Definitions, config_from_files
from dagster_gcp.gcs import gcs_pickle_io_manager, gcs_resource

from teamster.core.powerschool.assets.db import students
from teamster.core.resources.sqlalchemy import oracle
from teamster.core.resources.ssh import ssh_resource

defs = Definitions(
    assets=[students],
    resources={
        "db": oracle.configured(
            config_from_files(["src/teamster/core/powerschool/config/db.yaml"])
        ),
        "ssh": ssh_resource.configured(
            config_from_files(["src/teamster/core/powerschool/config/ssh.yaml"])
        ),
        "io_manager": gcs_pickle_io_manager.configured(
            config_from_files(["src/teamster/core/powerschool/config/io.yaml"])
        ),
        "gcs": gcs_resource.configured(
            config_from_files(["src/teamster/core/powerschool/config/io.yaml"])
        ),
    },
)

from dagster import Definitions
from dagster_gcp.gcs import gcs_pickle_io_manager, gcs_resource

from teamster.core.powerschool.assets.db import students
from teamster.core.resources.sqlalchemy import oracle
from teamster.core.resources.ssh import ssh_resource

defs = Definitions(
    assets=[students],
    resources={
        "db": oracle,
        "ssh": ssh_resource,
        "io_manager": gcs_pickle_io_manager,
        "gcs": gcs_resource,
    },
)

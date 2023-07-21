import re

from dagster import RunConfig, job

from teamster.core.fivetran.ops import SyncConfig, fivetran_start_sync_op
from teamster.kipptaf import CODE_LOCATION, fivetran

__all__ = []

for asset in fivetran.assets:
    connector_name = list(asset.group_names_by_key.values())[0]
    connector_id = re.match(
        pattern=r"fivetran_sync_(?P<connector_id>\w+)", string=asset.node_def.name
    ).groupdict()["connector_id"]

    @job(
        name=f"{CODE_LOCATION}_fivetran_{connector_name}_start_sync_job",
        config=RunConfig(
            ops={
                connector_name: SyncConfig(
                    connector_id=connector_id, yield_materializations=False
                )
            }
        ),
    )
    def _job():
        fivetran_sync_op_aliased = fivetran_start_sync_op.alias(connector_name)
        fivetran_sync_op_aliased()

    __all__.append(_job)

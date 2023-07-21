import re

from dagster import AssetSelection, define_asset_job, job  # , RunConfig, configured

from teamster.core.fivetran.ops import SyncConfig, fivetran_sync_op
from teamster.kipptaf import CODE_LOCATION, fivetran

# op_config = {}
# for asset in fivetran.assets:
#     connector_id = re.match(
#         pattern=r"fivetran_sync_(?P<connector_id>\w+)", string=asset.node_def.name
#     ).groupdict()["connector_id"]

#     op_config[connector_id] = SyncConfig(
#         connector_id=connector_id, yield_materializations=False
#     )


# @job(config=RunConfig(ops=op_config))
@job
def fivetran_sync_job():
    for asset in fivetran.assets:
        connector_id = re.match(
            pattern=r"fivetran_sync_(?P<connector_id>\w+)", string=asset.node_def.name
        ).groupdict()["connector_id"]

        fivetran_sync_op.configured(
            config_or_config_fn=SyncConfig(
                connector_id=connector_id, yield_materializations=False
            ),
            name=connector_id,
        )
        # fivetran_sync_op_aliased = fivetran_sync_op.alias(connector_id)
        # fivetran_sync_op_aliased()


__all__ = [
    fivetran_sync_job,
]

for asset in fivetran.assets:
    __all__.append(
        define_asset_job(
            name=(
                f"{CODE_LOCATION}_fivetran_"
                f"{list(asset.group_names_by_key.values())[0]}_asset_job"
            ),
            selection=AssetSelection.keys(*list(asset.keys)),
        )
    )

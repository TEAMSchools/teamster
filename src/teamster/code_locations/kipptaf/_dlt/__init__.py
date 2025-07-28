from teamster.code_locations.kipptaf._dlt.illuminate.assets import (
    assets as illuminate_assets,
)
from teamster.code_locations.kipptaf._dlt.illuminate.schedules import schedules

# from teamster.code_locations.kipptaf._dlt.salesforce.assets import (
#     assets as salesforce_assets,
# )
from teamster.code_locations.kipptaf._dlt.zendesk.assets import assets as zendesk_assets

assets = [
    *illuminate_assets,
    *zendesk_assets,
    # salesforce_assets,
]

__all__ = [
    "assets",
    "schedules",
]

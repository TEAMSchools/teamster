from teamster.code_locations.kipptaf._dlt.illuminate.assets import (
    assets as illuminate_assets,
)
<<<<<<< HEAD
from teamster.code_locations.kipptaf._dlt.illuminate.schedules import (
    schedules as illuminate_schedules,
)
from teamster.code_locations.kipptaf._dlt.zendesk.assets import assets as zendesk_assets
from teamster.code_locations.kipptaf._dlt.zendesk.schedules import (
    schedules as zendesk_schedules,
)

assets = [
    *illuminate_assets,
    *zendesk_assets,
]

schedules = [
    *illuminate_schedules,
    *zendesk_schedules,
=======
from teamster.code_locations.kipptaf._dlt.illuminate.schedules import schedules

# from teamster.code_locations.kipptaf._dlt.salesforce.assets import (
#     assets as salesforce_assets,
# )
# from teamster.code_locations.kipptaf._dlt.zendesk.assets import assets as zendesk_assets

assets = [
    *illuminate_assets,
    # *zendesk_assets,
    # salesforce_assets,
>>>>>>> main
]

__all__ = [
    "assets",
    "schedules",
]

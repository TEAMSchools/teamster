from teamster.code_locations.kipptaf.zendesk.assets import zendesk_user_sync
from teamster.code_locations.kipptaf.zendesk.schedules import schedules

assets = [
    zendesk_user_sync,
]

__all__ = [
    "assets",
    "schedules",
]

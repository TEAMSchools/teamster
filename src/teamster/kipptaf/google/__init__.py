from .directory.assets import (
    google_directory_nonpartitioned_assets,
    google_directory_partitioned_assets,
)
from .directory.jobs import (
    google_directory_nonpartitioned_asset_job,
    google_directory_role_assignments_sync_job,
    google_directory_user_sync_job,
)
from .directory.schedules import (
    google_directory_nonpartitioned_asset_schedule,
    google_directory_role_assignments_sync_schedule,
    google_directory_user_sync_schedule,
)
from .forms.assets import google_forms_assets
from .forms.jobs import google_forms_asset_job
from .forms.schedules import google_forms_asset_job_schedule
from .sheets.assets import google_sheets_assets
from .sheets.sensors import google_sheets_sensor

assets = [
    google_directory_nonpartitioned_assets,
    google_directory_partitioned_assets,
    google_forms_assets,
    google_sheets_assets,
]

jobs = [
    google_directory_nonpartitioned_asset_job,
    google_directory_role_assignments_sync_job,
    google_directory_user_sync_job,
    google_forms_asset_job,
]

schedules = [
    google_directory_nonpartitioned_asset_schedule,
    google_directory_role_assignments_sync_schedule,
    google_directory_user_sync_schedule,
    google_forms_asset_job_schedule,
]

sensors = [
    google_sheets_sensor,
]

__all__ = [
    assets,
    jobs,
    schedules,
    sensors,
]

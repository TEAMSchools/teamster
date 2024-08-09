from teamster.code_locations.kipptaf._google import (
    appsheet,
    bigquery,
    directory,
    drive,
    forms,
    sheets,
)

assets = [
    *appsheet.assets,
    *directory.assets,
    *forms.assets,
    *sheets.assets,
]

schedules = [
    *directory.schedules,
    *forms.schedules,
]

sensors = [
    *bigquery.sensors,
    *drive.sensors,
    *sheets.sensors,
]

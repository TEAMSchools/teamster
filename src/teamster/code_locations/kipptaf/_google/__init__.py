from teamster.code_locations.kipptaf._google import (
    appsheet,
    bigquery,
    directory,
    forms,
    sheets,
)

assets = [
    *directory.assets,
    *forms.assets,
]

asset_specs = [
    *appsheet.asset_specs,
    *sheets.asset_specs,
]

schedules = [
    *directory.schedules,
    *forms.schedules,
]

sensors = [
    *bigquery.sensors,
    *forms.sensors,
    *sheets.sensors,
]

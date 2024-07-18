from teamster.code_locations.kipptaf._google import directory, drive, forms, sheets

assets = [
    *directory.assets,
    *forms.assets,
    *sheets.assets,
]

jobs = [
    *directory.jobs,
]

schedules = [
    *directory.schedules,
    *forms.schedules,
]

sensors = [
    *sheets.sensors,
    *drive.sensors,
]

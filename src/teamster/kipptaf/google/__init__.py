from teamster.kipptaf.google import directory, forms, sheets

assets = [
    *directory.assets,
    *forms.assets,
    *sheets.assets,
]

jobs = [
    *directory.jobs,
    *forms.jobs,
]

schedules = [
    *directory.schedules,
    *forms.schedules,
]

sensors = [
    *sheets.sensors,
]

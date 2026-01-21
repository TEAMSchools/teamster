from teamster.code_locations.kippnewark import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippnewark.pearson.assets import (
    njgpa,
    njsla,
    njsla_science,
    student_list_report,
    student_test_update,
)
from teamster.libraries.couchdrop.sensors import build_couchdrop_sftp_sensor

couchdrop_sftp_sensor = build_couchdrop_sftp_sensor(
    code_location=CODE_LOCATION,
    local_timezone=LOCAL_TIMEZONE,
    asset_selection=[
        njgpa,
        njsla_science,
        njsla,
        student_list_report,
        student_test_update,
    ],
    minimum_interval_seconds=(60 * 10),
    folder_id="1B24uuik9MuBf-pKrrRn1lt3cWVtVAYJE",
    exclude_dirs=[
        f"/data-team/{CODE_LOCATION}/edplan",
        f"/data-team/{CODE_LOCATION}/pearson/parcc",
        f"/data-team/{CODE_LOCATION}/pearson/start_strong",
    ],
)

sensors = [
    couchdrop_sftp_sensor,
]

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.knowbe4.schema import ENROLLMENT_SCHEMA
from teamster.libraries.knowbe4.assets import build_knowbe4_asset

training_enrollments = build_knowbe4_asset(
    code_location=CODE_LOCATION,
    resource="training/enrollments",
    params={"include_employee_number": "true", "exclude_archived_users": "false"},
    schema=ENROLLMENT_SCHEMA,
)

assets = [
    training_enrollments,
]

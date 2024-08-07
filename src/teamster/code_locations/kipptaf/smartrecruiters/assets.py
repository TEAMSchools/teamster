from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.smartrecruiters.schema import (
    APPLICANTS_SCHEMA,
    APPLICATIONS_SCHEMA,
)
from teamster.libraries.smartrecruiters.assets import build_smartrecruiters_report_asset

applicants = build_smartrecruiters_report_asset(
    asset_key=[CODE_LOCATION, "smartrecruiters", "applicants"],
    report_id="e841aa3f-b037-4976-b75f-8ef43e177a45",
    schema=APPLICANTS_SCHEMA,
)

applications = build_smartrecruiters_report_asset(
    asset_key=[CODE_LOCATION, "smartrecruiters", "applications"],
    report_id="878d114e-8e48-4ffe-a81b-cb3c92ee653f",
    schema=APPLICATIONS_SCHEMA,
)

assets = [
    applicants,
    applications,
]

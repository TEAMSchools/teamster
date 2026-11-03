from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.nsc.schema import STUDENT_TRACKER_SCHEMA
from teamster.libraries.sftp.assets import build_sftp_folder_asset

# slugify matches replacements before it swaps "-" for the "_" separator
STUDENT_TRACKER_REPLACEMENTS = [["2-year-4-year", "two_year_four_year"]]

student_tracker = build_sftp_folder_asset(
    asset_key=[CODE_LOCATION, "nsc", "student_tracker"],
    remote_dir_regex=r"/data-team/kipptaf/nsc/student_tracker",
    remote_file_regex=r".+\.csv",
    ssh_resource_key="ssh_couchdrop",
    avro_schema=STUDENT_TRACKER_SCHEMA,
    slugify_replacements=STUDENT_TRACKER_REPLACEMENTS,
)

assets = [
    student_tracker,
]

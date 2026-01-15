from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.nsc.schema import STUDENT_TRACKER_SCHEMA
from teamster.libraries.sftp.assets import build_sftp_folder_asset

student_tracker = build_sftp_folder_asset(
    asset_key=[CODE_LOCATION, "nsc", "student_tracker"],
    remote_dir_regex=r"/data-team/kipptaf/nsc/student_tracker",
    remote_file_regex=r".+\.csv",
    ssh_resource_key="ssh_couchdrop",
    avro_schema=STUDENT_TRACKER_SCHEMA,
    slugify_replacements=[["2_year_4_year", "two_year_four_year"]],
)

assets = [
    student_tracker,
]

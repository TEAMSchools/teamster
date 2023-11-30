from dagster import StaticPartitionsDefinition

from teamster.core.google.directory.assets import (
    build_google_directory_assets,
    build_google_directory_partitioned_assets,
)

from ... import CODE_LOCATION

google_directory_nonpartitioned_assets = build_google_directory_assets(
    code_location=CODE_LOCATION
)

google_directory_partitioned_assets = build_google_directory_partitioned_assets(
    code_location=CODE_LOCATION,
    partitions_def=StaticPartitionsDefinition(
        [
            "group-students-camden@teamstudents.org",
            "group-students-miami@teamstudents.org",
            "group-students-newark@teamstudents.org",
        ]
    ),
)

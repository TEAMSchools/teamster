from dagster import MultiPartitionsDefinition, StaticPartitionsDefinition

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.amplify.dibels.schema import (
    DATA_FARMING_SCHEMA,
    PROGRESS_EXPORT_SCHEMA,
)
from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.libraries.amplify.dibels.assets import build_amplify_dds_report_asset

date_partitions_def = FiscalYearPartitionsDefinition(
    start_date="2024-07-01", start_month=7, timezone=LOCAL_TIMEZONE.name
)

data_farming = build_amplify_dds_report_asset(
    code_location=CODE_LOCATION,
    partitions_def=MultiPartitionsDefinition(
        {"date": date_partitions_def, "grade": StaticPartitionsDefinition(["_ALL_"])}
    ),
    schema=DATA_FARMING_SCHEMA,
    report="DataFarming",
    report_kwargs={
        "AssessmentPeriod": "_ALL_",
        "StudentFilter": "any",
        "Fields[]": [
            2,  # Student ID
            41,  # Benchmark Statuses
            43,  # School Percentiles
            44,  # District Percentiles
            45,  # National DDS Percentiles
            47,  # Outcome Measures
            48,  # Assessment Dates
            # 1,  # Student Name
            # 3,  # Secondary ID
            # 4,  # Date of Birth
            # 5,  # Demographics
            # 21,  # Schools
            # 22,  # Class Names
            # 23,  # Secondary Class Names
            # 25,  # Teacher Names
            # 26,  # District IDs
            # 27,  # School IDs
            # 49,  # Assessment Forms
            # 51,  # Remote Testing Status
            # 50,  # Zones of Growth (must select all periods)
            # 61,  # Move Out Dates
            # 62,  # Data System Internal IDs
        ],
        # "GrowthMeasure": 16240,  # Composite
    },
)

progress_export = build_amplify_dds_report_asset(
    code_location=CODE_LOCATION,
    partitions_def=MultiPartitionsDefinition(
        {
            "date": date_partitions_def,
            "grade": StaticPartitionsDefinition(["107", "108"]),
        }
    ),
    schema=PROGRESS_EXPORT_SCHEMA,
    report="ProgressExport",
    report_kwargs={
        "Compatibility": "Data Farming (Standard)",
        "Format": "One Score Per Row",
        "IncludedData[]": [
            "assessmentform",
            "classroomname",
            "d1_raceethnicity",
            "date",
            "dds_internal_ids",
            "district_instid",
            "dob",
            "lastname",
            "primary_id",
            "schoolname",
            "secondary_id",
            "secondaryclass",
            "teacher",
        ],
    },
)

assets = [
    data_farming,
    progress_export,
]

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.branchingminds.schema import (
    ACADEMIC_PROGRESS_MONITORING_SCHEMA,
    BENCHMARKS_UNIVERSAL_SCREENERS_SCHEMA,
    CURRENT_STUDENT_TIER_LEVELS_SCHEMA,
    DAILY_INTERVENTION_SESSIONS_SCHEMA,
    GOALS_SCHEMA,
    INTERVENTION_NOTES_SCHEMA,
    INTERVENTION_PLANS_SCHEMA,
    NEW_BEHAVIOR_INCIDENT_REPORT_SCHEMA,
    TIERS_SCHEMA,
)
from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.libraries.sftp.assets import build_sftp_file_asset

# BrM writes each export to /exports/<file stem>/<file stem>.csv
EXPORTS = {
    "academic_progress_monitoring": (
        "academic_progress_monitoring",
        ACADEMIC_PROGRESS_MONITORING_SCHEMA,
    ),
    "benchmarks_universal_screeners": (
        "benchmarks_universal_screeners_w_demographics",
        BENCHMARKS_UNIVERSAL_SCREENERS_SCHEMA,
    ),
    "current_student_tier_levels": (
        "current_student_tier_levels",
        CURRENT_STUDENT_TIER_LEVELS_SCHEMA,
    ),
    "daily_intervention_sessions": (
        "daily_intervention_sessions",
        DAILY_INTERVENTION_SESSIONS_SCHEMA,
    ),
    "goals": ("goals_with_demographics_export", GOALS_SCHEMA),
    "intervention_notes": (
        "intervention_notes_with_demographics_export",
        INTERVENTION_NOTES_SCHEMA,
    ),
    "intervention_plans": (
        "intervention_report_with_demographics_export",
        INTERVENTION_PLANS_SCHEMA,
    ),
    "new_behavior_incident_report": (
        "new_behavior_incident_report_w_demographics",
        NEW_BEHAVIOR_INCIDENT_REPORT_SCHEMA,
    ),
    "tiers": ("tiers_with_demographics_export", TIERS_SCHEMA),
}

partitions_def = FiscalYearPartitionsDefinition(
    start_date="2026-07-01", timezone=str(LOCAL_TIMEZONE), start_month=7
)

assets = [
    build_sftp_file_asset(
        asset_key=[CODE_LOCATION, "branchingminds", name],
        remote_dir_regex=f"/exports/{stem}",
        remote_file_regex=rf"{stem}\.csv",
        ssh_resource_key="ssh_branchingminds",
        avro_schema=avro_schema,
        partitions_def=partitions_def,
        current_partition_only=True,
    )
    for name, (stem, avro_schema) in EXPORTS.items()
]

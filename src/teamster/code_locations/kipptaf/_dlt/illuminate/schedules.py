from dagster import ScheduleDefinition

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE

asset_key_prefix = f"{CODE_LOCATION}/dlt/illuminate"

illuminate_dlt_hourly_asset_job_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__dlt__illuminate__hourly_asset_job_schedule",
    cron_schedule=["0 0 * * *", "0 17 * * *", "0 14 * * 3", "0 15 * * 5"],
    execution_timezone=str(LOCAL_TIMEZONE),
    target=[
        f"{asset_key_prefix}/dna_assessments/agg_student_responses",
        f"{asset_key_prefix}/dna_assessments/agg_student_responses_group",
        f"{asset_key_prefix}/dna_assessments/agg_student_responses_standard",
        f"{asset_key_prefix}/dna_assessments/assessment_grade_levels",
        f"{asset_key_prefix}/dna_assessments/assessment_standards",
        f"{asset_key_prefix}/dna_assessments/assessments",
        f"{asset_key_prefix}/dna_assessments/assessments_reporting_groups",
        f"{asset_key_prefix}/dna_assessments/students_assessments",
    ],
)

illuminate_dlt_daily_asset_job_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__dlt__illuminate__daily_asset_job_schedule",
    cron_schedule="0 0 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    target=[
        f"{asset_key_prefix}/codes/dna_scopes",
        f"{asset_key_prefix}/codes/dna_subject_areas",
        f"{asset_key_prefix}/dna_assessments/performance_band_sets",
        f"{asset_key_prefix}/dna_assessments/performance_bands",
        f"{asset_key_prefix}/dna_assessments/reporting_groups",
        f"{asset_key_prefix}/dna_repositories/fields",
        f"{asset_key_prefix}/dna_repositories/repositories",
        f"{asset_key_prefix}/dna_repositories/repository_443",
        f"{asset_key_prefix}/dna_repositories/repository_444",
        f"{asset_key_prefix}/dna_repositories/repository_445",
        f"{asset_key_prefix}/dna_repositories/repository_446",
        f"{asset_key_prefix}/dna_repositories/repository_447",
        f"{asset_key_prefix}/dna_repositories/repository_448",
        f"{asset_key_prefix}/dna_repositories/repository_449",
        f"{asset_key_prefix}/dna_repositories/repository_450",
        f"{asset_key_prefix}/dna_repositories/repository_451",
        f"{asset_key_prefix}/dna_repositories/repository_452",
        f"{asset_key_prefix}/dna_repositories/repository_453",
        f"{asset_key_prefix}/dna_repositories/repository_454",
        f"{asset_key_prefix}/dna_repositories/repository_455",
        f"{asset_key_prefix}/dna_repositories/repository_456",
        f"{asset_key_prefix}/dna_repositories/repository_457",
        f"{asset_key_prefix}/dna_repositories/repository_458",
        f"{asset_key_prefix}/dna_repositories/repository_459",
        f"{asset_key_prefix}/dna_repositories/repository_460",
        f"{asset_key_prefix}/dna_repositories/repository_461",
        f"{asset_key_prefix}/dna_repositories/repository_462",
        f"{asset_key_prefix}/dna_repositories/repository_463",
        f"{asset_key_prefix}/dna_repositories/repository_464",
        f"{asset_key_prefix}/dna_repositories/repository_465",
        f"{asset_key_prefix}/dna_repositories/repository_466",
        f"{asset_key_prefix}/dna_repositories/repository_467",
        f"{asset_key_prefix}/dna_repositories/repository_468",
        f"{asset_key_prefix}/dna_repositories/repository_469",
        f"{asset_key_prefix}/dna_repositories/repository_470",
        f"{asset_key_prefix}/dna_repositories/repository_471",
        f"{asset_key_prefix}/dna_repositories/repository_472",
        f"{asset_key_prefix}/dna_repositories/repository_grade_levels",
        f"{asset_key_prefix}/public/sessions",
        f"{asset_key_prefix}/public/student_session_aff",
        f"{asset_key_prefix}/public/students",
        f"{asset_key_prefix}/public/users",
        f"{asset_key_prefix}/standards/standards",
    ],
)

schedules = [
    illuminate_dlt_daily_asset_job_schedule,
    illuminate_dlt_hourly_asset_job_schedule,
]

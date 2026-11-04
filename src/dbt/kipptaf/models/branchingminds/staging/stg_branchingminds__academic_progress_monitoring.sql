with
    academic_progress_monitoring as (
        select
            subject_area,
            assessment_family,
            assessment_name,
            assessment_grade_level,
            notes,
            staff,
            district,

            _dagster_partition_fiscal_year as source_fiscal_year,

            safe_cast(score_id as int64) as score_id,
            safe_cast(student_number as int64) as student_number,
            safe_cast(school_id as int64) as school_id,
            safe_cast(school_year as int64) as school_year,
            safe_cast(score as numeric) as score,
            safe_cast(assessment_date as date) as assessment_date,
        from
            {{
                source(
                    "branchingminds",
                    "src_branchingminds__academic_progress_monitoring",
                )
            }}
    )

    {{
        dbt_utils.deduplicate(
            relation="academic_progress_monitoring",
            partition_by="score_id",
            order_by="source_fiscal_year desc",
        )
    }}

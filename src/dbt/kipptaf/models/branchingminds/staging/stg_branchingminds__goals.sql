with
    goals as (
        select
            goal_state,
            subject_area,
            assessment_name,
            goal,
            goal_status,
            staff,
            district,

            _dagster_partition_fiscal_year as source_fiscal_year,

            safe_cast(goal_id as int64) as goal_id,
            safe_cast(student_number as int64) as student_number,
            safe_cast(school_id as int64) as school_id,
            safe_cast(school_year as int64) as school_year,
            safe_cast(goal_score as numeric) as goal_score,
            safe_cast(end_date as date) as end_date,
        from {{ source("branchingminds", "src_branchingminds__goals") }}
    )

    {{
        dbt_utils.deduplicate(
            relation="goals",
            partition_by="goal_id",
            order_by="source_fiscal_year desc",
        )
    }}

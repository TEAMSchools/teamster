with
    daily_intervention_sessions as (
        select
            intervention_name,
            intervention_subject_area,
            session_missed_reason,
            intervention_location,
            intervention_group_size,
            staff_delivering_intervention,
            staff_email,
            district,

            _dagster_partition_fiscal_year as source_fiscal_year,

            safe_cast(intervention_session_id as int64) as intervention_session_id,
            safe_cast(intervention_plan_id as int64) as intervention_plan_id,
            safe_cast(student_number as int64) as student_number,
            safe_cast(school_id as int64) as school_id,
            safe_cast(school_year as int64) as school_year,
            safe_cast(
                delivered_minutes_in_session as int64
            ) as delivered_minutes_in_session,
            safe_cast(
                planned_minutes_per_session as int64
            ) as planned_minutes_per_session,
            safe_cast(planned_sessions_per_week as int64) as planned_sessions_per_week,
            safe_cast(session_week as date) as session_week,
            safe_cast(session_date as date) as session_date,
        from
            {{
                source(
                    "branchingminds",
                    "src_branchingminds__daily_intervention_sessions",
                )
            }}
    )

    {{
        dbt_utils.deduplicate(
            relation="daily_intervention_sessions",
            partition_by="intervention_session_id",
            order_by="source_fiscal_year desc",
        )
    }}

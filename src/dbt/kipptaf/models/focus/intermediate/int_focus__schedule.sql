with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippmiami_focus", "int_focus__schedule"),
                ]
            )
        }}
    ),

    schedule_raw as (
        select
            *, {{ extract_source_project("union_relations") }} as _dbt_source_project,
        from union_relations
    )

    -- Focus schedules some students into the same course period twice: a
    -- same-day-superseded stint (start_date = end_date) alongside the current
    -- open one (end_date null). Keep the open stint per
    -- (student_id, course_period_id); demote marking_period_id as a secondary
    -- tiebreak in case a genuine full-year/term-specific duplicate ever occurs.
    {{
        dbt_utils.deduplicate(
            relation="schedule_raw",
            partition_by="student_id, course_period_id",
            order_by="(end_date is not null) asc, (marking_period_id is not null) asc",
        )
    }}

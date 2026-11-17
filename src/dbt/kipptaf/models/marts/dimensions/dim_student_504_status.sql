with
    enrollments as (
        select
            student_number,
            _dbt_source_project,
            academic_year,
            entrydate,

            -- exitdate is the first day after the stint
            coalesce(
                date_sub(exitdate, interval 1 day), cast('9999-12-31' as date)
            ) as enrollment_end,
        from {{ ref("int_students__student_enrollment_union") }}
        -- graduate placeholder rows have no entry date
        where entrydate is not null
    ),

    spans as (
        select
            p.student_number,
            p._dbt_source_project,
            p.is_current_plan,

            e.academic_year,
            e.entrydate,

            greatest(p.plan_start_date, e.entrydate) as effective_date_start,
            least(p.plan_end_date, e.enrollment_end) as effective_date_end,
        from {{ ref("int_students__section_504_plans") }} as p
        inner join
            enrollments as e
            on p.student_number = e.student_number
            and p._dbt_source_project = e._dbt_source_project
            and p.plan_start_date <= e.enrollment_end
            and p.plan_end_date >= e.entrydate
    )

select
    _dbt_source_project,

    effective_date_start as effective_date_start_key,
    effective_date_end as effective_date_end_key,

    is_current_plan,

    {{
        dbt_utils.generate_surrogate_key(
            ["student_number", "_dbt_source_project", "effective_date_start"]
        )
    }} as student_504_status_key,

    {{ student_key("student_number") }} as student_key,

    {{
        student_enrollment_key(
            "student_number",
            "_dbt_source_project",
            "academic_year",
            "entrydate",
        )
    }} as student_enrollment_key,
from spans

with
    enrollments as (
        select
            student_number,
            _dbt_source_project,
            academic_year,
            entrydate,

            -- exitdate is half-open (first day after the stint); subtract 1
            -- day so stints that share a boundary date do not overlap
            coalesce(
                date_sub(exitdate, interval 1 day), cast('9999-12-31' as date)
            ) as enrollment_end,
        from {{ ref("int_students__student_enrollment_union") }}
        -- graduate placeholder rows carry no entry date to clip against
        where entrydate is not null
    ),

    spans as (
        select
            student_number,
            _dbt_source_project,
            academic_year,
            `subject`,
            bucket,
            bucket_store,
            assignment_date,

            -- exit_date is half-open, like the enrollment exit
            coalesce(
                date_sub(exit_date, interval 1 day), cast('9999-12-31' as date)
            ) as span_end,
        from {{ ref("int_students__bucket_assignments") }}
    ),

    clipped as (
        select
            s.student_number,
            s._dbt_source_project,
            s.`subject`,
            s.bucket,
            s.bucket_store,
            s.assignment_date,

            e.academic_year,
            e.entrydate,

            greatest(s.assignment_date, e.entrydate) as effective_date_start,
            least(s.span_end, e.enrollment_end) as effective_date_end,
        from spans as s
        -- academic_year keeps a span with no exit date out of later years
        inner join
            enrollments as e
            on s.student_number = e.student_number
            and s._dbt_source_project = e._dbt_source_project
            and s.academic_year = e.academic_year
            and s.assignment_date <= e.enrollment_end
            and s.span_end >= e.entrydate
        -- an assignment entered and exited on the same day covers no date
        where s.assignment_date <= s.span_end
    )

select
    _dbt_source_project,
    `subject`,
    bucket,
    bucket_store,
    assignment_date,

    effective_date_start as effective_date_start_key,
    effective_date_end as effective_date_end_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "student_number",
                "_dbt_source_project",
                "academic_year",
                "entrydate",
                "subject",
                "assignment_date",
            ]
        )
    }} as student_bucket_status_key,

    {{ student_key("student_number") }} as student_key,

    {{
        student_enrollment_key(
            "student_number", "_dbt_source_project", "academic_year", "entrydate"
        )
    }} as student_enrollment_key,

    effective_date_end = '9999-12-31' as is_current,

    row_number() over (
        partition by
            student_number, _dbt_source_project, academic_year, entrydate, `subject`
        order by effective_date_start desc, assignment_date desc
    )
    = 1 as is_latest_in_enrollment,
from clipped

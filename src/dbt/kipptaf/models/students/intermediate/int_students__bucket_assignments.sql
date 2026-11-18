with
    assignment_union as (
        select
            p.academic_year,
            p._dbt_source_project,
            p.student_number,
            p.`subject`,
            p.bucket,
            p.assignment_date,
            p.exit_date,
            p.n_active_assignments,

            'powerschool' as bucket_store,
        from {{ ref("int_powerschool__bucket_programs") }} as p
        inner join
            {{ ref("int_extracts__student_enrollments") }} as co
            on p.student_number = co.student_number
            and p.academic_year = co.academic_year
            and p._dbt_source_project = co._dbt_source_project
            and co.rn_year = 1

        union all

        select
            academic_year,
            _dbt_source_project,
            student_number,
            `subject`,
            bucket,
            assignment_date,
            exit_date,
            n_active_assignments,

            'focus' as bucket_store,
        from {{ ref("int_focus__bucket_memberships") }}
    )

select
    academic_year,
    _dbt_source_project,
    student_number,
    `subject`,
    bucket,
    bucket_store,
    assignment_date,
    exit_date,
    n_active_assignments,

    row_number() over (
        partition by academic_year, _dbt_source_project, student_number, `subject`
        order by assignment_date desc
    ) as rn_assignment_year_desc,
from assignment_union

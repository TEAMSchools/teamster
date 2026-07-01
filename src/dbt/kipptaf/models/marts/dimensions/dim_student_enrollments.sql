with
    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    homeroom as (
        select
            student_enrollment_key,
            entry_date,

            lead_teacher_staff_key as homeroom_teacher_staff_key,
        from {{ ref("dim_student_section_enrollments") }}
        where is_homeroom and student_enrollment_key is not null
    ),

    homeroom_resolved as (
        {{
            dbt_utils.deduplicate(
                relation="homeroom",
                partition_by="student_enrollment_key",
                order_by="entry_date desc",
            )
        }}
    ),

    enrollments as (
        select
            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "enr.student_number",
                        "enr._dbt_source_project",
                        "enr.academic_year",
                        "enr.entrydate",
                    ]
                )
            }} as student_enrollment_key,

            {{ dbt_utils.generate_surrogate_key(["enr.student_number"]) }}
            as student_key,

            sch.location_key,

            enr.entrydate as entry_date_key,
            enr.exitdate as exit_date_key,

            enr.academic_year,
            enr.grade_level,
            enr.cohort_primary as graduation_year,
            enr.is_retained_year,
            enr.year_in_network,
        from {{ ref("int_powerschool__student_enrollment_union") }} as enr
        left join
            {{ ref("stg_powerschool__schools") }} as sch
            on enr.schoolid = sch.school_number
            and enr._dbt_source_project = sch._dbt_source_project
    )

select
    e.student_enrollment_key,
    e.student_key,
    e.location_key,
    e.entry_date_key,
    e.exit_date_key,
    e.academic_year,
    e.grade_level,
    e.graduation_year,
    e.is_retained_year,
    e.year_in_network,

    hr.homeroom_teacher_staff_key,
from enrollments as e
left join
    homeroom_resolved as hr on e.student_enrollment_key = hr.student_enrollment_key

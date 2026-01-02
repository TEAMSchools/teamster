with
    temp_deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=ref("int_finalsite__status_report"),
                partition_by="surrogate_key",
                order_by="effective_date",
            )
        }}
    ),

    enrollment_type_checks as (
        select
            academic_year,
            student_number,
            student_first_name,
            student_last_name,

            entrydate,
            exitdate,

            'Returner' as enrollment_type,

            sum(if(date_diff(exitdate, entrydate, day) >= 7, 1, 0)) over (
                partition by student_number
            ) as enrollment_type_check,

            row_number() over (partition by student_number order by entrydate) as rn,

        from {{ ref("int_extracts__student_enrollments") }}
        where
            academic_year >= {{ var("current_academic_year") - 1 }}
            and grade_level != 99
        qualify enrollment_type_check != 0
    ),

    ps_match_academic_year as (
        select
            e.academic_year,
            e.school,
            e.student_number,
            e.student_first_name,
            e.student_last_name,
            e.grade_level,
            e.enroll_status,

        from {{ ref("int_extracts__student_enrollments") }} as e
        left join
            enrollment_type_checks as c
            on e.student_number = c.student_number
            and c.rn = 1
        where
            e.academic_year = {{ var("current_academic_year") }} and e.grade_level != 99
    )

select
    t.*,

    x.overall_status,
    x.funnel_status,
    x.status_category,
    x.detailed_status_ranking,
    x.powerschool_enroll_status,
    x.valid_detailed_status,
    x.offered,
    x.conversion,
    x.offered_ops,
    x.conversion_ops,

from temp_deduplicate as t
left join
    {{ ref("stg_google_sheets__finalsite_status_crosswalk") }} as x
    -- fix this later when int view is fixed
    on t.academic_year = x.enrollment_academic_year
    and t.enrollment_type = x.enrollment_type
    and t.detailed_status = x.detailed_status

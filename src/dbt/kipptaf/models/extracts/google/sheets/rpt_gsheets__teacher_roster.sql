with
    -- primary_indicator + the April-1 as-of filter is assumed to yield one row
    -- per teacher; the upstream grain is (employee_number, effective_date_start,
    -- position_id), so the PK unique test guards against a teacher ever holding
    -- two concurrent primary positions spanning the as-of date.
    staff as (
        select
            powerschool_teacher_number,
            employee_number,
            job_title,
            level_of_education,
            reports_to_employee_number,
        from {{ ref("int_people__staff_roster_history") }}
        where
            primary_indicator
            and powerschool_teacher_number is not null
            and date(
                ({{ var("current_academic_year") }} + 1),
                4,
                1
            ) between effective_date_start and coalesce(
                effective_date_end, cast('9999-12-31' as date)
            )
    )

select
    sr.powerschool_teacher_number,
    sr.job_title,
    sr.level_of_education,
    sr.reports_to_employee_number,

    os.final_score,
    os.final_tier,

    ye.years_at_kipp_total,
    ye.years_experience_total,
    ye.years_teaching_total,

    {{ var("current_academic_year") }} as academic_year,
from staff as sr
left join
    {{ ref("int_performance_management__overall_scores") }} as os
    on sr.employee_number = os.employee_number
    and os.academic_year = {{ var("current_academic_year") }}
left join
    {{ ref("int_people__years_experience") }} as ye
    on sr.employee_number = ye.employee_number
    and ye.academic_year = {{ var("current_academic_year") }}

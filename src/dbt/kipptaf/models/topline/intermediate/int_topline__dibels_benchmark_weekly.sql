with
    benchmarks as (
        select
            student_number,
            academic_year,
            `period`,
            sync_date,
            measure_standard_level,
            measure_standard_level_int,
        from {{ ref("int_amplify__all_assessments") }}
        where measure_name = 'Composite'
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="benchmarks",
                partition_by="student_number, academic_year, period",
                order_by="sync_date desc",
            )
        }}
    )

select
    cw.student_number,
    cw.state_studentnumber,
    cw.student_name,
    cw.academic_year,
    cw.week_start_monday,
    cw.week_end_sunday,
    cw.week_number_academic_year,
    cw.region,
    cw.school_level,
    cw.schoolid,
    cw.school,
    cw.grade_level,
    cw.gender,
    cw.ethnicity,
    cw.iep_status,
    cw.is_504,
    cw.lep_status,
    cw.gifted_and_talented,
    cw.entrydate,
    cw.exitdate,
    cw.enroll_status,
    cw.is_enrolled_week,

    rt.name as test_round,

    'ELA' as discipline,

    case
        when amp.measure_standard_level_int > 2
        then 1
        when amp.measure_standard_level_int <= 2
        then 0
    end as is_proficient,
from {{ ref("int_extracts__student_enrollments_weeks") }} as cw
inner join
    {{ ref("stg_google_sheets__reporting__terms") }} as rt
    on cw.academic_year = rt.academic_year
    and cw.region = rt.city
    and cw.week_start_monday between rt.start_date and rt.end_date
    and rt.type = 'LITEX'
left join
    deduplicate as amp
    on cw.student_number = amp.student_number
    and cw.academic_year = amp.academic_year
    and rt.name = amp.`period`

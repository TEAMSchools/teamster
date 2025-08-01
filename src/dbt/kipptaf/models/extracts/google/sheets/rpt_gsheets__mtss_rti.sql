with
    iready_long as (
        select
            student_id,
            academic_year_int,

            lower(subject) as subject,
            concat(
                most_recent_overall_relative_placement,
                ' (',
                most_recent_completion_date,
                ')'
            ) as iready_most_recent,
        from {{ ref("base_iready__diagnostic_results") }}
        where rn_subj_year = 1
    ),

    iready_pivot as (
        select student_id, academic_year_int, reading, math,
        from
            iready_long
            pivot (max(iready_most_recent) for subject in ('reading', 'math'))
    ),

    dibels_recent as (
        select
            academic_year,
            student_number,
            client_date,
            measure_standard_level,

            'Reading' as iready_subject,

            row_number() over (
                partition by academic_year, student_number order by client_date desc
            ) as rn_benchmark,
        from {{ ref("int_amplify__all_assessments") }}
        where measure_standard = 'Composite'
    ),

    gpa as (
        select studentid, _dbt_source_relation, schoolid, yearid, gpa_y1,
        from {{ ref("int_powerschool__gpa_term") }}
        where is_current
    ),

    roster as (
        select
            co.academic_year,
            co.region,
            co.school,
            co.student_number,
            co.student_name,
            co.grade_level,
            co.advisory,
            co.boy_status,
            co.iep_status,
            co.lep_status,
            co.is_504,
            co.ada,

            g.gpa_y1 as gpa_y1_current,

            case
                when co.enroll_status = 0
                then 'Currently Enrolled'
                when co.enroll_status = 2
                then 'Transferred Out'
                when co.enroll_status = 3
                then 'Graduated'
                when co.enroll_status = -1
                then 'Pre-Enrolled'
            end as enrollment_status,
            lag(co.ada, 1) over (
                partition by co.student_number order by co.academic_year asc
            ) as ada_prev_year,

            coalesce(ir.reading, 'No Data') as most_recent_iready_reading_current,
            coalesce(ir.math, 'No Data') as most_recent_iready_math_current,
            lag(coalesce(ir.reading, 'No Data'), 1) over (
                partition by co.student_number order by co.academic_year asc
            ) as most_recent_iready_reading_prev_year,
            lag(coalesce(ir.math, 'No Data'), 1) over (
                partition by co.student_number order by co.academic_year asc
            ) as most_recent_iready_math_prev_year,

            coalesce(
                dr.measure_standard_level, 'No Data'
            ) as most_recent_dibels_composite_current,
            lag(coalesce(dr.measure_standard_level, 'No Data'), 1) over (
                partition by co.student_number order by co.academic_year asc
            ) as most_recent_dibels_composite_prev_year,

            lag(g.gpa_y1, 1) over (
                partition by co.student_number order by co.academic_year asc
            ) as gpa_y1_prev_year,

            coalesce(sr.days_suspended_oss, 0) as days_suspended_oss_current,
            coalesce(sr.days_suspended_all, 0) as days_suspended_all_current,
            lag(coalesce(sr.days_suspended_oss, 0), 1) over (
                partition by co.student_number order by co.academic_year asc
            ) as days_suspended_oss_prev_year,
            lag(coalesce(sr.days_suspended_all, 0), 1) over (
                partition by co.student_number order by co.academic_year asc
            ) as days_suspended_all_prev_year,
            coalesce(sr.referral_count_all, 0) as referral_count_current,
            lag(coalesce(sr.referral_count_all, 0), 1) over (
                partition by co.student_number order by co.academic_year asc
            ) as referral_count_prev_year,
        from {{ ref("int_extracts__student_enrollments") }} as co
        left join
            iready_pivot as ir
            on co.student_number = ir.student_id
            and co.academic_year = ir.academic_year_int
        left join
            dibels_recent as dr
            on co.student_number = dr.student_number
            and co.academic_year = dr.academic_year
            and dr.rn_benchmark = 1
        left join
            gpa as g
            on co.studentid = g.studentid
            and co.schoolid = g.schoolid
            and co.yearid = g.yearid
            and {{ union_dataset_join_clause(left_alias="co", right_alias="g") }}
        left join
            {{ ref("int_deanslist__referral_suspension_rollup") }} as sr
            on co.student_number = sr.student_school_id
            and co.academic_year = sr.create_ts_academic_year
    )

select *,
from roster
where academic_year = {{ var("current_academic_year") }}

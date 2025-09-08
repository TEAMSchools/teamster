with
    iready_long as (
        select
            student_id,
            academic_year_int,
            overall_scale_score,

            lower(`subject`) as `subject`,

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
        select
            student_id,
            academic_year_int,
            iready_most_recent_reading as reading,
            iready_most_recent_math as math,
            iready_most_recent_scale_reading,
            iready_most_recent_scale_math,
        from
            iready_long pivot (
                max(iready_most_recent) as iready_most_recent,
                max(overall_scale_score) as iready_most_recent_scale for `subject`
                in ('reading', 'math')
            )
    ),

    dibels_recent as (
        select
            academic_year,
            student_number,
            measure_standard_level,
            measure_standard_score,

            row_number() over (
                partition by academic_year, student_number order by client_date desc
            ) as rn_benchmark,
        from {{ ref("int_amplify__all_assessments") }}
        where measure_standard = 'Composite'
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

            ir.iready_most_recent_scale_reading
            as iready_most_recent_scale_reading_current,
            ir.iready_most_recent_scale_math as iready_most_recent_scale_math_current,

            dr.measure_standard_score as most_recent_dibels_scale_current,

            coalesce(ir.reading, 'No Data') as most_recent_iready_reading_current,
            coalesce(ir.math, 'No Data') as most_recent_iready_math_current,

            coalesce(
                dr.measure_standard_level, 'No Data'
            ) as most_recent_dibels_composite_current,

            coalesce(sr.days_suspended_oss, 0) as days_suspended_oss_current,
            coalesce(sr.days_suspended_all, 0) as days_suspended_all_current,
            coalesce(sr.referral_count_all, 0) as referral_count_current,

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

            lag(coalesce(ir.reading, 'No Data'), 1) over (
                partition by co.student_number order by co.academic_year asc
            ) as most_recent_iready_reading_prev_year,
            lag(coalesce(ir.math, 'No Data'), 1) over (
                partition by co.student_number order by co.academic_year asc
            ) as most_recent_iready_math_prev_year,

            lag(ir.iready_most_recent_scale_reading, 1) over (
                partition by co.student_number order by co.academic_year asc
            ) as most_recent_iready_reading_scale_prev_year,
            lag(ir.iready_most_recent_scale_math, 1) over (
                partition by co.student_number order by co.academic_year asc
            ) as most_recent_iready_math_scale_prev_year,

            lag(coalesce(dr.measure_standard_level, 'No Data'), 1) over (
                partition by co.student_number order by co.academic_year asc
            ) as most_recent_dibels_composite_prev_year,

            lag(dr.measure_standard_score, 1) over (
                partition by co.student_number order by co.academic_year asc
            ) as most_recent_dibels_scale_prev_year,

            lag(g.gpa_y1, 1) over (
                partition by co.student_number order by co.academic_year asc
            ) as gpa_y1_prev_year,

            lag(coalesce(sr.days_suspended_oss, 0), 1) over (
                partition by co.student_number order by co.academic_year asc
            ) as days_suspended_oss_prev_year,
            lag(coalesce(sr.days_suspended_all, 0), 1) over (
                partition by co.student_number order by co.academic_year asc
            ) as days_suspended_all_prev_year,
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
            {{ ref("int_powerschool__gpa_term") }} as g
            on co.studentid = g.studentid
            and co.schoolid = g.schoolid
            and co.yearid = g.yearid
            and {{ union_dataset_join_clause(left_alias="co", right_alias="g") }}
            and g.is_current
        left join
            {{ ref("int_deanslist__referral_suspension_rollup") }} as sr
            on co.student_number = sr.student_school_id
            and co.academic_year = sr.create_ts_academic_year
            and sr.term = 'Y1'
        where
            co.academic_year >= {{ var("current_academic_year") - 1 }}
            and co.rn_year = 1
    ),

    current_year as (
        select
            academic_year,
            region,
            school,
            student_number,
            student_name,
            grade_level,
            advisory,
            boy_status,
            iep_status,
            lep_status,
            is_504,
            ada,
            gpa_y1_current,
            most_recent_iready_reading_current,
            most_recent_iready_math_current,
            iready_most_recent_scale_reading_current,
            iready_most_recent_scale_math_current,
            most_recent_dibels_composite_current,
            most_recent_dibels_scale_current,
            days_suspended_oss_current,
            days_suspended_all_current,
            referral_count_current,
            enrollment_status,
            ada_prev_year,
            most_recent_iready_reading_prev_year,
            most_recent_iready_math_prev_year,
            most_recent_dibels_composite_prev_year,
            most_recent_dibels_scale_prev_year,
            gpa_y1_prev_year,
            days_suspended_oss_prev_year,
            days_suspended_all_prev_year,
            referral_count_prev_year,
        from roster
        where academic_year = {{ var("current_academic_year") }}
    ),

    iready_reading_percentiles as (
        select
            student_number,
            academic_year,
            round(
                percent_rank() over (
                    partition by school, grade_level
                    order by iready_most_recent_scale_reading_current asc
                ),
                2
            ) as iready_reading_current_year_percentile
        from current_year
        where iready_most_recent_scale_reading_current is not null
    ),

    iready_math_percentiles as (
        select
            student_number,
            academic_year,
            round(
                percent_rank() over (
                    partition by school, grade_level
                    order by iready_most_recent_scale_math_current asc
                ),
                2
            ) as iready_math_current_year_percentile
        from current_year
        where iready_most_recent_scale_math_current is not null
    ),

    dibels_percentiles as (
        select
            student_number,
            academic_year,
            round(
                percent_rank() over (
                    partition by school, grade_level
                    order by most_recent_dibels_scale_current asc
                ),
                2
            ) as dibels_scale_current_percentile
        from current_year
        where most_recent_dibels_scale_current is not null
    )

select
    cy.*,
    irp_r.iready_reading_current_year_percentile,
    irp_m.iready_math_current_year_percentile,
    dp.dibels_scale_current_percentile
from current_year as cy
left join
    iready_reading_percentiles as irp_r
    on cy.student_number = irp_r.student_number
    and cy.academic_year = irp_r.academic_year
left join
    iready_math_percentiles as irp_m
    on cy.student_number = irp_m.student_number
    and cy.academic_year = irp_m.academic_year
left join
    dibels_percentiles as dp
    on cy.student_number = dp.student_number
    and cy.academic_year = dp.academic_year
where cy.enrollment_status = 'Currently Enrolled'

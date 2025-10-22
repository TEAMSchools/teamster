with
    athletic_eligibility as (
        select academic_year, student_number, `quarter`, athletic_eligibility,
        from
            {{ ref("int_students__athletic_eligibility") }} unpivot (
                athletic_eligibility for `quarter` in (
                    q1_ae_status as 'Q1',
                    q2_ae_status as 'Q2',
                    q3_ae_status as 'Q3',
                    q4_ae_status as 'Q4'
                )
            )

    )

select
    co.student_number,
    co.academic_year,
    co.cumulative_y1_gpa as gpa_cum,
    co.cumulative_y1_gpa_projected as gpa_cum_projected,
    co.earned_credits_cum as grades_y1_credits_projected,

    term,

    gpa.gpa_term,
    gpa.gpa_y1,

    p.overall_status as promo_status_overall,
    p.attendance_status as promo_status_attendance,
    p.academic_status as promo_status_grades,
    p.n_failing as grades_y1_failing_projected,
    p.n_failing_core,
    p.ada_term_running,
    p.projected_credits_y1_term,

    ae.athletic_eligibility,

    null as promo_status_lit,
    cast(null as string) as promo_status_math,
    null as promo_status_qa_math,
    null as grades_y1_credits_enrolled,

    case
        co.grade_level when 9 then 25 when 10 then 50 when 11 then 85 when 12 then 120
    end as promo_credits_needed,

    coalesce(
        p.dibels_composite_level_recent_str, '(No Data)'
    ) as dibels_composite_recent,
    coalesce(p.iready_reading_recent, '(No Data)') as iready_reading_recent,
    coalesce(p.iready_math_recent, '(No Data)') as iready_math_recent,

    coalesce(
        concat('Level ', p.star_reading_level_recent), '(No Data)'
    ) as star_reading_level_recent,

    coalesce(
        concat('Level ', p.star_math_level_recent), '(No Data)'
    ) as star_math_level_recent,

    coalesce(
        concat('Level ', p.fast_ela_level_recent), '(No Data)'
    ) as fast_ela_level_recent,

    coalesce(
        concat('Level ', p.fast_math_level_recent), '(No Data)'
    ) as fast_math_level_recent,
from {{ ref("int_extracts__student_enrollments") }} as co
cross join unnest(['Q1', 'Q2', 'Q3', 'Q4']) as term
left join
    {{ ref("int_powerschool__gpa_term") }} as gpa
    on co.studentid = gpa.studentid
    and co.yearid = gpa.yearid
    and term = gpa.term_name
    and {{ union_dataset_join_clause(left_alias="co", right_alias="gpa") }}
left join
    {{ ref("int_reporting__promotional_status") }} as p
    on co.student_number = p.student_number
    and co.academic_year = p.academic_year
    and term = p.term_name
left join
    athletic_eligibility as ae
    on co.student_number = ae.student_number
    and co.academic_year = ae.academic_year
    and term = ae.quarter
where co.academic_year = {{ var("current_academic_year") }} and co.rn_year = 1

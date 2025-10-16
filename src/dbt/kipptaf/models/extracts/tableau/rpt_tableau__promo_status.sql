select
    co.student_number,
    co.lastfirst,
    co.region,
    co.school_level,
    co.school_abbreviation,
    co.grade_level,
    co.advisory_name,
    co.advisor_lastfirst as advisor_name,
    co.lep_status,
    co.ethnicity,
    co.gender,
    co.is_retained_year,
    co.is_retained_ever,

    rt.name as term,
    rt.is_current,

    ps.ada_term_running,
    ps.n_absences_y1_running,
    ps.iready_reading_recent,
    ps.iready_math_recent,
    ps.n_failing,
    ps.n_failing_core,
    ps.projected_credits_y1_term,
    ps.projected_credits_cum,
    ps.dibels_composite_level_recent,
    ps.star_math_level_recent,
    ps.star_reading_level_recent,
    ps.fast_ela_level_recent,
    ps.fast_math_level_recent,
    ps.attendance_status,
    ps.attendance_status_hs_detail,
    ps.academic_status,
    ps.exemption,
    ps.manual_retention,
    ps.overall_status as promo_status_overall,

    if(co.spedlep like 'SPED%', 'Has IEP', co.spedlep) as iep_status,
from {{ ref("int_extracts__student_enrollments") }} as co
inner join
    {{ ref("stg_google_sheets__reporting__terms") }} as rt
    on co.academic_year = rt.academic_year
    and co.schoolid = rt.school_id
    and rt.type = 'RT'
left join
    {{ ref("int_reporting__promotional_status") }} as ps
    on co.student_number = ps.student_number
    and co.academic_year = ps.academic_year
    and rt.name = ps.term_name
where
    co.academic_year = {{ var("current_academic_year") }}
    and co.rn_year = 1
    and co.enroll_status = 0

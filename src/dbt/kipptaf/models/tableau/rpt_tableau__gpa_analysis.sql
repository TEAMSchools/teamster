{{ config(enabled=False) }}
select
    co.student_number,
    co.lastfirst,
    co.gender,
    co.ethnicity,
    co.enroll_status,
    co.cohort,
    co.academic_year,
    co.region,
    co.school_level,
    co.school_name,
    co.grade_level,
    co.team,
    co.iep_status,
    co.lep_status,
    co.c_504_status,
    co.is_pathways,
    co.lunchstatus,
    co.year_in_network,
    co.boy_status,
    co.is_retained_year,
    co.is_retained_ever,
    co.rn_undergrad,

    kt.sf_contact_id as salesforce_id,

    gpad.reporting_term,
    gpad.term_name,
    gpad.semester,
    gpad.is_curterm,
    gpad.gpa_term,
    gpad.gpa_points_total_term,
    gpad.weighted_gpa_points_term,
    gpad.grade_avg_term,
    gpad.gpa_semester,
    gpad.gpa_points_total_semester,
    gpad.weighted_gpa_points_semester,
    gpad.total_credit_hours_semester,
    gpad.grade_avg_semester,
    gpad.gpa_y1,
    gpad.gpa_y1_unweighted,
    gpad.gpa_points_total_y1,
    gpad.weighted_gpa_points_y1,
    gpad.total_credit_hours,
    gpad.grade_avg_y1,
    gpad.n_failing_y1,

    gpac.cumulative_y1_gpa,
    gpac.cumulative_y1_gpa_unweighted,
    gpac.cumulative_y1_gpa_projected,
    gpac.cumulative_y1_gpa_projected_s1,
    gpac.earned_credits_cum,
    gpac.earned_credits_cum_projected,
    gpac.earned_credits_cum_projected_s1,
    gpac.potential_credits_cum,
    gpac.core_cumulative_y1_gpa,
    gpac.cumulative_y1_gpa_projected_s1_unweighted
from powerschool.cohort_identifiers_static as co
left join gabby.alumni.ktc_roster as kt on kt.student_number = co.student_number
left join
    powerschool.gpa_detail as gpad
    on co.student_number = gpad.student_number
    and co.academic_year = gpad.academic_year
    and co.schoolid = gpad.schoolid
    and co.db_name = gpad.db_name
left join
    powerschool.gpa_cumulative as gpac
    on co.studentid = gpac.studentid
    and co.schoolid = gpac.schoolid
    and co.db_name = gpac.db_name
where co.school_level in ('MS', 'HS') and co.rn_year = 1

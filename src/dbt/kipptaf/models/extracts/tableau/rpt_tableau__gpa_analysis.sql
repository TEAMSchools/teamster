select
    sr.student_number,
    sr.lastfirst,
    sr.gender,
    sr.ethnicity,
    sr.enroll_status,
    sr.cohort,
    sr.academic_year,
    sr.region,
    sr.school_level,
    sr.school_name,
    sr.grade_level,
    sr.advisory_name as team,
    sr.spedlep as iep_status,
    sr.lep_status,
    sr.is_504 as c_504_status,
    sr.is_self_contained as is_pathways,
    sr.lunch_status as lunchstatus,
    sr.year_in_network,
    sr.boy_status,
    sr.is_retained_year,
    sr.is_retained_ever,
    sr.rn_undergrad,

    ktc.id as salesforce_id,

    null as reporting_term,
    gt.term_name,
    gt.semester,
    gt.is_current as is_curterm,
    gt.gpa_term,
    gt.gpa_points_total_term,
    gt.weighted_gpa_points_term,
    gt.grade_avg_term,
    gt.gpa_semester,
    gt.gpa_points_total_semester,
    gt.weighted_gpa_points_semester,
    gt.total_credit_hours_semester,
    gt.grade_avg_semester,
    gt.gpa_y1,
    gt.gpa_y1_unweighted,
    gt.gpa_points_total_y1,
    gt.weighted_gpa_points_y1,
    gt.total_credit_hours,
    gt.grade_avg_y1,
    gt.n_failing_y1,

    gc.cumulative_y1_gpa,
    gc.cumulative_y1_gpa_unweighted,
    gc.cumulative_y1_gpa_projected,
    gc.cumulative_y1_gpa_projected_s1,
    gc.earned_credits_cum,
    gc.earned_credits_cum_projected,
    gc.earned_credits_cum_projected_s1,
    gc.potential_credits_cum,
    gc.core_cumulative_y1_gpa,
    gc.cumulative_y1_gpa_projected_s1_unweighted,
from {{ ref("base_powerschool__student_enrollments") }} as sr
left join
    {{ ref("stg_kippadb__contact") }} as ktc
    on sr.student_number = ktc.school_specific_id
left join
    {{ ref("int_powerschool__gpa_term") }} as gt
    on sr.studentid = gt.studentid
    and sr.yearid = gt.yearid
    and sr.schoolid = gt.schoolid
    and {{ union_dataset_join_clause(left_alias="sr", right_alias="gt") }}
left join
    {{ ref("int_powerschool__gpa_cumulative") }} as gc
    on sr.studentid = gc.studentid
    and sr.schoolid = gc.schoolid
    and {{ union_dataset_join_clause(left_alias="sr", right_alias="gc") }}
where sr.school_level in ('MS', 'HS') and sr.rn_year = 1

select
    enr._dbt_source_relation,
    enr.studentid,
    enr.student_number,
    enr.student_name,
    enr.enroll_status,
    enr.cohort,
    enr.gender,
    enr.ethnicity,
    enr.yearid,
    enr.region,
    enr.school_level,
    enr.schoolid,
    enr.school,
    enr.grade_level as most_recent_grade_level,
    enr.advisory,
    enr.year_in_school,
    enr.year_in_network,
    enr.rn_undergrad,
    enr.is_self_contained as is_pathways,
    enr.is_out_of_district,
    enr.is_retained_year,
    enr.is_retained_ever,
    enr.lunch_status,
    enr.lep_status,
    enr.gifted_and_talented,
    enr.iep_status,
    enr.is_504,
    enr.salesforce_id,
    enr.ktc_cohort,
    enr.is_counseling_services,
    enr.is_student_athlete,
    enr.ada_above_or_at_80,
    enr.hos,

    gc.cumulative_y1_gpa,
    gc.cumulative_y1_gpa_unweighted,
    gc.cumulative_y1_gpa_projected,
    gc.cumulative_y1_gpa_projected_s1,
    gc.cumulative_y1_gpa_projected_s1_unweighted,
    gc.core_cumulative_y1_gpa,

    round(enr.ada, 3) as most_recent_ada,

from {{ ref("int_extracts__student_enrollments") }} as enr
left join
    {{ ref("int_powerschool__gpa_cumulative") }} as gc
    on enr.studentid = gc.studentid
    and enr.schoolid = gc.schoolid
    and {{ union_dataset_join_clause(left_alias="enr", right_alias="gc") }}
where
    enr.rn_undergrad = 1
    and not enr.is_out_of_district
    and enr.school_level in ('MS', 'HS')
    and enr.enroll_status in (0, 3)

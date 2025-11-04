select
    _dbt_source_relation,
    studentid,
    student_number,
    student_name,
    enroll_status,
    cohort,
    gender,
    ethnicity,
    yearid,
    region,
    school_level_alt as school_level,
    schoolid,
    school,
    grade_level as most_recent_grade_level,
    advisory,
    year_in_school,
    year_in_network,
    rn_undergrad,
    is_self_contained as is_pathways,
    is_out_of_district,
    is_retained_year,
    is_retained_ever,
    lunch_status,
    lep_status,
    gifted_and_talented,
    iep_status,
    is_504,
    salesforce_id,
    ktc_cohort,
    is_counseling_services,
    is_student_athlete,
    ada_above_or_at_80,
    hos,
    cumulative_y1_gpa,
    cumulative_y1_gpa_unweighted,
    cumulative_y1_gpa_projected,
    cumulative_y1_gpa_projected_s1,
    cumulative_y1_gpa_projected_s1_unweighted,
    core_cumulative_y1_gpa,
    ada as most_recent_ada,

    if(
        cumulative_y1_gpa is not null
        and ktc_cohort >= {{ var("current_academic_year") }}
        and cumulative_y1_gpa_unweighted > cumulative_y1_gpa,
        true,
        false
    ) as is_cum_gpa_flag,

from {{ ref("int_extracts__student_enrollments") }}
where
    rn_undergrad = 1
    and not is_out_of_district
    and school_level_alt in ('MS', 'HS')
    and enroll_status in (0, 3)
    and region != 'Paterson'

select
    gcy._dbt_source_relation,
    gcy._dbt_source_project,
    gcy.studentid,
    gcy.academic_year,
    gcy.schoolid,
    gcy.grade_level,
    gcy.is_projected,
    gcy.earned_credits_cum,
    gcy.potential_gpa_credits_cum,
    gcy.cumulative_y1_gpa,
    gcy.cumulative_y1_gpa_unweighted,

    e.student_number,
    e.student_name,
    e.academic_year_display,
    e.region,
    e.school_level_alt as school_level,
    e.school,
    e.enroll_status,
    e.cohort,
    e.graduation_year,
    e.gender,
    e.ethnicity,
    e.advisory,
    e.year_in_school,
    e.year_in_network,
    e.rn_undergrad,
    e.is_self_contained as is_pathways,
    e.is_retained_year,
    e.is_retained_ever,
    e.student_slideback,
    e.lunch_status,
    e.lep_status,
    e.gifted_and_talented,
    e.iep_status,
    e.is_504,
    e.salesforce_id,
    e.ktc_cohort,
    e.is_counseling_services,
    e.is_student_athlete,
    e.ada,
    e.ada_above_or_at_80,
    e.hos,
    e.school_leader,
    e.school_leader_tableau_username,

from {{ ref("int_powerschool__gpa_cumulative_year") }} as gcy
/* the inner join on the year's rn_year = 1 enrollment (including schoolid)
   dedupes the union model's student x school x year grain to one row per
   student-year, keyed to the primary enrollment school */
inner join
    {{ ref("int_extracts__student_enrollments") }} as e
    on gcy.studentid = e.studentid
    and gcy.academic_year = e.academic_year
    and gcy.schoolid = e.schoolid
    and gcy._dbt_source_project = e._dbt_source_project
where
    e.rn_year = 1
    and not e.is_out_of_district
    /* status guard drops pre-registered (-1, which can pass
       is_enrolled_recent) and invalid (1) rows */
    and e.enroll_status in (0, 2, 3)
    and e.is_enrolled_recent
    /* Miami hard-excluded: region unsupported in the rebuilt dashboard
       (#4340) */
    -- TODO(#4340): add Paterson once PS gradebook data is populated
    and e.region in ('Newark', 'Camden')

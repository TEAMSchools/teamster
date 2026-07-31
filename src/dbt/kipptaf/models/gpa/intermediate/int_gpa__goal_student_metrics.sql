select
    sr.academic_year,
    sr.region,
    sr.schoolid,
    sr.grade_level,
    sr.student_number,
    sr.cumulative_y1_gpa_projected_unweighted as cumulative_gpa_unweighted,

    gt.gpa_y1 as y1_gpa_weighted,
    gt.gpa_y1_unweighted as y1_gpa_unweighted,

    -- TODO(#4581): populate from on-pace follow-on (Task 6)
    cast(null as boolean) as is_on_pace,
    -- TODO(#4581): populate from on-pace follow-on (Task 6)
    cast(null as boolean) as is_on_pace_denominator,
from {{ ref("int_extracts__student_enrollments") }} as sr
left join
    {{ ref("int_powerschool__gpa_term") }} as gt
    on sr.studentid = gt.studentid
    and sr.yearid = gt.yearid
    and sr.schoolid = gt.schoolid
    and sr._dbt_source_project = gt._dbt_source_project
    and gt.is_current
where
    sr.school_level = 'HS'
    and sr.rn_year = 1
    /* date-derived, not status-derived: true when the enrollment ran to the end
       of the school year or is active today. enroll_status is student-level and
       current-only, so it drops graduated seniors from every completed year —
       for AY2025 that was 382 of 398 grade-12 students, reporting the cohort at
       0 percent attainment. */
    and sr.is_enrolled_recent
    /* TODO(#4581): Paterson is excluded until int_powerschool__gpa_term and
       int_powerschool__gpa_cumulative union kipppaterson (both are
       newark/camden/miami only today). Without this, Paterson HS students carry
       null GPA measures yet still count in org-level denominators, silently
       deflating the rate. */
    and sr._dbt_source_project != 'kipppaterson'

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
where sr.school_level = 'HS' and sr.rn_year = 1 and sr.enroll_status = 0

-- Downstream Lineage Verification -- Root Cause
--
-- For each row collegeboard_ap_downstream_lineage_missing_rows surfaced,
-- checks whether the student has ANY course enrollment with a matching
-- ap_course_subject (regardless of the dashboard's specific join filters) to
-- distinguish 'PowerSchool tagging gap' (a sibling course with the right
-- subject exists but wasn't picked up -- see
-- collegeboard_ap_course_tagging.sql) from 'genuinely tested without taking
-- the class' (a real, expected scenario per College Board's rules -- not a
-- bug to chase; if EVERY missing row is this case, the root cause is
-- actually rpt_tableau__ap_assessment_dashboard's join structure itself --
-- see https://github.com/TEAMSchools/teamster/issues/4391).
--
-- Pass the specific student numbers found missing, and the target academic
-- year, at compile time:
-- --vars '{missing_student_numbers: [123456, 234567], current_academic_year: <year>}'
select
    ce.ap_course_subject,
    ce.courses_course_name,
    ce.is_dropped_section,

    se.student_number,
from {{ ref("base_powerschool__course_enrollments") }} as ce
inner join
    {{ ref("base_powerschool__student_enrollments") }} as se
    on ce.cc_studentid = se.studentid
    and ce.cc_academic_year = se.academic_year
    and ce._dbt_source_project = se._dbt_source_project
where
    se.student_number in unnest({{ var("missing_student_numbers", []) }})
    and ce.cc_academic_year = {{ var("current_academic_year") }}
    and ce.ap_course_subject is not null

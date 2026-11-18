-- DDI Course Subject Crosswalk Audit
--
-- Lists current-year-enrollment courses missing from the course subject
-- crosswalk sheet (ddi-stack skill, rollover step 7). The output is a triage
-- list for humans, not a defect list: homeroom, lunch, and co-curricular
-- courses are expected here and stay off the sheet. Hand the result to
-- c3/academic ops to confirm which courses are tested subjects (connected to
-- Illuminate results, state testing, both, or eventually Focus Apex), then
-- add only the confirmed rows to the crosswalk named range.
--
-- Miami is off the DDI stack; drop that filter when Focus assessments onboard.
-- Compile with dbt and run the compiled SQL read-only (BigQuery MCP).
select
    enr.courses_course_number,

    any_value(enr.courses_course_name) as course_name,
    any_value(enr.courses_credittype) as credittype,
    count(distinct enr.students_student_number) as n_students,
from {{ ref("base_powerschool__course_enrollments") }} as enr
left join
    {{ ref("stg_google_sheets__assessments__course_subject_crosswalk") }} as cw
    on enr.courses_course_number = cw.powerschool_course_number
where
    enr.cc_academic_year = {{ var("current_academic_year") }}
    and enr._dbt_source_project != 'kippmiami'
    and not enr.is_dropped_section
    and cw.powerschool_course_number is null
group by enr.courses_course_number
order by n_students desc

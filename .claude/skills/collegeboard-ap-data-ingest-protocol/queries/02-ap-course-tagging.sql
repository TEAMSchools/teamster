-- AP Course Tagging Check
--
-- ap_course_subject comes from PowerSchool's NJ state course-extension
-- table (stg_powerschool__s_nj_crs_x, joined by coursesdcid) - a course-setup
-- field a human sets directly in PowerSchool, independent of the crosswalk
-- sheet. is_ap_course is literally defined as `ap_course_subject is not
-- null`, so a course that already has the field set can't fail this check
-- by definition - the real gap is a course whose NAME signals AP but was
-- never tagged. Flag unconditionally: a course still gets flagged even if
-- its exam type happens to already resolve fine through a different,
-- correctly-tagged course elsewhere.
--
-- Scoped to academic_year >= 2024 per user direction (older history isn't
-- actionable). This is a PowerSchool course-setup miss with no PII involved -
-- hand the result to whoever owns PowerSchool course setup; no write access
-- to PowerSchool here.

select distinct
  cc_academic_year,
  cc_course_number,
  courses_course_name,
  ap_course_subject
from `teamster-332318`.kipptaf_powerschool.base_powerschool__course_enrollments
where cc_academic_year >= 2024
  and regexp_contains(courses_course_name, r'\bAP\b')
  and ap_course_subject is null
order by cc_academic_year, courses_course_name

-- To find which district/region owns a flagged course (needed to route the
-- fix), follow up with:
--
-- select distinct _dbt_source_relation, cc_schoolid
-- from `teamster-332318`.kipptaf_powerschool.base_powerschool__course_enrollments
-- where cc_academic_year = <flagged_year>
--   and cc_course_number = '<flagged_course_number>'
--
-- then resolve cc_schoolid to a school name via
-- kipptaf_powerschool.base_powerschool__student_enrollments
-- (schoolid/school_name columns, same academic_year).

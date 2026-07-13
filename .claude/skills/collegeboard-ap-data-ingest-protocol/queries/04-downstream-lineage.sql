-- Downstream Lineage Verification
--
-- Confirms a crosswalk fix actually reaches int_collegeboard__ap_unpivot and
-- the CARAT dashboard (rpt_tableau__ap_assessment_dashboard), not just the
-- crosswalk sheet. rpt_tableau__ap_assessment_dashboard lives in the
-- kipptaf_tableau dataset (not a generic "extracts" dataset - confirmed via
-- INFORMATION_SCHEMA, don't guess). The dashboard's actual Tableau workbook
-- is the "College Admission Readiness Assessments Tracker (CARAT)" exposure
-- in src/dbt/kipptaf/models/exposures/tableau.yml
-- (name: college_admission_readiness_assessments_tracker_carat, LSID
-- 286156c4-2f9e-4983-926b-63c9b11f44f4, Dagster-owned refresh cron
-- "0 6 * * *") - use the exposure file to find the workbook, don't guess at
-- names. Since the BQ table is a live VIEW, this count comparison already
-- reflects what a live Tableau connection would show; only cross-check via
-- the Tableau MCP (get-workbook / list-datasources with the LSID) if the
-- workbook turns out to use an extract instead.
--
-- Replace <academic_year> below with the year the crosswalk fix targeted.

select
  (select count(*) from `teamster-332318`.kipptaf_dbt_test__audit.int_collegeboard__ap_unpivot__crosswalk_resolves) as remaining_crosswalk_gaps,
  (select count(*) from `teamster-332318`.kipptaf_collegeboard.int_collegeboard__ap_unpivot where academic_year = <academic_year>) as unpivot_rows,
  (select count(*) from `teamster-332318`.kipptaf_tableau.rpt_tableau__ap_assessment_dashboard where academic_year = <academic_year> and test_name is not null) as dashboard_scored_rows;

-- If unpivot_rows and dashboard_scored_rows don't reconcile, find exactly
-- which exam scores are missing from the dashboard:

select
  u.powerschool_student_number,
  u.exam_code_description,
  u.ps_ap_course_subject_code,
  u.ap_course_name
from `teamster-332318`.kipptaf_collegeboard.int_collegeboard__ap_unpivot u
where u.academic_year = <academic_year>
  and not exists (
    select 1
    from `teamster-332318`.kipptaf_tableau.rpt_tableau__ap_assessment_dashboard d
    where d.academic_year = <academic_year>
      and d.student_number = u.powerschool_student_number
      and d.ps_ap_course_subject_code = u.ps_ap_course_subject_code
      and d.test_name is not null
  );

-- For each missing row, check whether the student has ANY course enrollment
-- with a matching ap_course_subject (regardless of the dashboard's specific
-- join filters) to distinguish "PowerSchool tagging gap" (a sibling course
-- with the right subject exists but wasn't picked up - see
-- 02-ap-course-tagging.sql) from "genuinely tested without taking the class"
-- (a real, expected scenario per College Board's rules - not a bug to
-- chase; if EVERY missing row is this case, the root cause is actually
-- rpt_tableau__ap_assessment_dashboard's join structure itself - see
-- https://github.com/TEAMSchools/teamster/issues/4391):

select
  se.student_number, ce.ap_course_subject, ce.courses_course_name, ce.is_dropped_section
from `teamster-332318`.kipptaf_powerschool.base_powerschool__course_enrollments ce
join `teamster-332318`.kipptaf_powerschool.base_powerschool__student_enrollments se
  on se.studentid = ce.cc_studentid
  and se.academic_year = ce.cc_academic_year
  and regexp_extract(se._dbt_source_relation, r'(kipp\w+)_') = regexp_extract(ce._dbt_source_relation, r'(kipp\w+)_')
where se.student_number in (<missing_student_numbers>)
  and ce.cc_academic_year = <academic_year>
  and ce.ap_course_subject is not null

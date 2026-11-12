-- trunk-ignore-all(sqlfluff)
-- fmt: off
-- cause C3 = dashboard: the response rollup dates the administration in a prior academic year, so the dashboard cannot place it in 2026
-- cause T1 = dashboard: below grade 9 the dashboard joins the student's tier on the assessment's subject, and only Text Study and Mathematics carry a tier, so this subject (Algebra I) gets none
-- cause T2 = dashboard: from grade 9 the dashboard joins the student's tier on the course's credit type, and only ENG and MATH carry a tier, so the student gets none
-- reproduce C3:
--  SELECT r.region, COUNT(*) AS n_rows
--  FROM `teamster-332318`.`kipptaf_assessments`.`int_assessments__response_rollup` AS r
--  INNER JOIN `teamster-332318`.`kipptaf_assessments`.`int_assessments__assessments_members` AS m
--    ON r.source = m.source AND r.assessment_id = m.assessment_id
--  INNER JOIN `teamster-332318`.`kipptaf_assessments`.`int_assessments__assessments_canonical` AS c
--    ON m.source = c.source AND m.canonical_assessment_id = c.canonical_assessment_id
--  WHERE r.is_internal_assessment AND r.response_type = 'overall' AND r.academic_year < 2026
--    AND COALESCE(c.administered_date, r.date_taken) >= DATE '2026-07-01'
--  GROUP BY r.region
-- reproduce T1:
--  SELECT d.grade_level, d.subject_area, COUNT(*) AS n_rows
--  FROM `teamster-332318`.`kipptaf_tableau`.`rpt_tableau__assessment_dashboard` AS d
--  WHERE d.academic_year = 2026 AND d.response_type = 'overall' AND d.is_normed_scope
--    AND d.grade_level < 9 AND d.subject_area = 'Algebra I' AND d.nj_student_tier IS NULL
--  GROUP BY d.grade_level, d.subject_area
-- reproduce T2:
--  SELECT d.grade_level, d.subject_area, COUNT(*) AS n_rows
--  FROM `teamster-332318`.`kipptaf_tableau`.`rpt_tableau__assessment_dashboard` AS d
--  WHERE d.academic_year = 2026 AND d.response_type = 'overall' AND d.is_normed_scope
--    AND d.grade_level >= 9 AND d.nj_student_tier IS NULL
--    AND d.subject_area IN ('English 100', 'Algebra I', 'Geometry Honors')
--  GROUP BY d.grade_level, d.subject_area

-- One proof for the cube_only bucket of all 8 bucket comparisons
-- (students-bucket-1/2/3-module, students-buckets-1-2-module and the 4
-- mastery-* twins). No predicate names a bucket, so the same SQL serves each;
-- confirm stores it once per comparison.
with
    -- the response rollup's academic years per student and assessment; the
    -- dashboard places a score in a year only through
    -- co.academic_year = asr.academic_year (rpt_tableau__assessment_dashboard)
    rollup_years as (
        select
            cast(student_number as string) as sn,
            cast(assessment_id as string) as aid,
            countif(academic_year = 2026) as n_2026,
            countif(academic_year < 2026) as n_prior,
        from `teamster-332318`.`kipptaf_assessments`.`int_assessments__response_rollup`
        group by 1, 2
    ),

    -- the dashboard's 2026 rows at the row grain, with the tier its
    -- d.filter_join = sf.assessment_dashboard_join left join found
    dashboard as (
        select
            cast(student_number as string) as sn,
            cast(assessment_id as string) as aid,
            response_type,
            standard_code,
            count(*) as n_rows,
            countif(nj_student_tier is null) as n_no_tier,
            max(grade_level) as max_grade,
            min(grade_level) as min_grade,
            logical_and(subject_area not in ('Text Study', 'Mathematics')) as all_untiered_subject,
        from `teamster-332318`.`kipptaf_tableau`.`rpt_tableau__assessment_dashboard`
        where academic_year = 2026
        group by 1, 2, 3, 4
    )

select
    u.__row,
    case
        -- int_assessments__response_rollup holds the pair only before 2026;
        -- the comparison is Academic Year 2026 and the dashboard joins
        -- co.academic_year = asr.academic_year
        when y.n_2026 = 0 and y.n_prior > 0
        then 'C3'
        -- filter_join: else asr.subject_area; assessment_dashboard_join:
        -- sj.illuminate_subject_area ('Text Study', 'Mathematics')
        when
            d.n_rows > 0
            and d.n_no_tier = d.n_rows
            and d.max_grade < 9
            and d.all_untiered_subject
        then 'T1'
        -- filter_join: when co.grade_level >= 9 then enr.courses_credittype;
        -- assessment_dashboard_join: sj.powerschool_credittype ('ENG', 'MATH')
        when d.n_rows > 0 and d.n_no_tier = d.n_rows and d.min_grade >= 9
        then 'T2'
        else 'UNEXPLAINED'
    end as cause,
from {unmatched} as u
left join
    rollup_years as y
    on cast(u.lea_student_identifier as string) = y.sn
    and cast(u.source_assessment_id as string) = y.aid
left join
    dashboard as d
    on cast(u.lea_student_identifier as string) = d.sn
    and cast(u.source_assessment_id as string) = d.aid
    and u.response_type is not distinct from d.response_type
    and u.response_type_code is not distinct from d.standard_code

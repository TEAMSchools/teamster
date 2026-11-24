-- trunk-ignore-all(sqlfluff)
-- fmt: off
-- cause C2 = dashboard: the dashboard reads only Illuminate and Focus assessments; Cube's view also holds i-Ready, DIBELS, STAR and state test scores
-- cause D1 = dashboard: no enrollment week in the score's region and year covers the assessment date (the responses join to int_extracts__student_enrollments_weeks)
-- cause D2 = dashboard: the student was not enrolled on the week's Sunday (co.is_enrolled_week_end)
-- cause D3 = dashboard: the student's enroll_status is not 0, 2 or 3
-- cause D4 = dashboard: the student is in an out-of-district placement (not co.is_out_of_district)
-- cause D5 = dashboard: the dashboard drops WPP modules (r.module_type != 'WPP')
-- cause D6 = dashboard: the dashboard keeps grades 0 to 12 only
-- cause D7 = dashboard: the dashboard drops assessments with no module type (r.module_type != 'WPP' is not true for a null)
-- cause D9 = dashboard: the dashboard's weekly enrollment rows mark the student not enrolled on the week's Sunday (co.is_enrolled_week_end is false in int_extracts__student_enrollments_weeks), though the student's enrollment dates cover that Sunday
-- unchanged C2 since 1bcae561576d2242f4b5ab68cd2c4663ce8f65fb63320d7962e39cac8d5098c4
-- unchanged C2 since 52acbccac9b3c2a0ac68952679ec03046e2965256713891eeef3f7d168b4d1bc
-- unchanged D1 since 1bcae561576d2242f4b5ab68cd2c4663ce8f65fb63320d7962e39cac8d5098c4
-- unchanged D1 since 52acbccac9b3c2a0ac68952679ec03046e2965256713891eeef3f7d168b4d1bc
-- unchanged D2 since 1bcae561576d2242f4b5ab68cd2c4663ce8f65fb63320d7962e39cac8d5098c4
-- unchanged D2 since 52acbccac9b3c2a0ac68952679ec03046e2965256713891eeef3f7d168b4d1bc
-- unchanged D3 since 1bcae561576d2242f4b5ab68cd2c4663ce8f65fb63320d7962e39cac8d5098c4
-- unchanged D3 since 52acbccac9b3c2a0ac68952679ec03046e2965256713891eeef3f7d168b4d1bc
-- unchanged D4 since 1bcae561576d2242f4b5ab68cd2c4663ce8f65fb63320d7962e39cac8d5098c4
-- unchanged D4 since 52acbccac9b3c2a0ac68952679ec03046e2965256713891eeef3f7d168b4d1bc
-- unchanged D5 since 1bcae561576d2242f4b5ab68cd2c4663ce8f65fb63320d7962e39cac8d5098c4
-- unchanged D5 since 52acbccac9b3c2a0ac68952679ec03046e2965256713891eeef3f7d168b4d1bc
-- unchanged D6 since 1bcae561576d2242f4b5ab68cd2c4663ce8f65fb63320d7962e39cac8d5098c4
-- unchanged D6 since 52acbccac9b3c2a0ac68952679ec03046e2965256713891eeef3f7d168b4d1bc
-- unchanged D7 since 52acbccac9b3c2a0ac68952679ec03046e2965256713891eeef3f7d168b4d1bc
-- saved 6ef4c49f109f0e8953f7c21b5aa6544b2fd052455ac1e28553d2e14d4235d74f

WITH rollup_rows AS (
  SELECT
    CAST(rr.student_number AS STRING) AS student,
    CAST(rr.assessment_id AS STRING) AS assessment,
    rr.student_number,
    rr.academic_year,
    rr.region,
    rr.administered_at,
    rr.module_type
  FROM `teamster-332318`.`kipptaf_assessments`.`int_assessments__response_rollup` AS rr
  WHERE rr.academic_year >= 2025
),
per_score AS (
  SELECT
    student,
    assessment,
    LOGICAL_OR(module_type = 'WPP') AS is_wpp,
    LOGICAL_AND(module_type IS NULL) AS is_untagged
  FROM rollup_rows
  GROUP BY student, assessment
),
weeks AS (
  SELECT
    r.student,
    r.assessment,
    LOGICAL_OR(cw.week_end_sunday BETWEEN co.entrydate AND co.last_enrolled_date) AS enrolled_week_end,
    LOGICAL_OR(
      cw.week_end_sunday BETWEEN co.entrydate AND co.last_enrolled_date
      AND co.enroll_status IN (0, 2, 3)
    ) AS status_ok,
    LOGICAL_OR(
      cw.week_end_sunday BETWEEN co.entrydate AND co.last_enrolled_date
      AND co.enroll_status IN (0, 2, 3)
      AND COALESCE(NOT co.is_out_of_district, FALSE)
    ) AS district_ok,
    LOGICAL_OR(
      cw.week_end_sunday BETWEEN co.entrydate AND co.last_enrolled_date
      AND co.enroll_status IN (0, 2, 3)
      AND COALESCE(NOT co.is_out_of_district, FALSE)
      AND co.grade_level BETWEEN 0 AND 12
    ) AS grade_ok
  FROM rollup_rows AS r
  INNER JOIN `teamster-332318`.`kipptaf_extracts`.`int_extracts__student_enrollments` AS co
    ON co.student_number = r.student_number
    AND co.academic_year = r.academic_year
    AND co.region = r.region
  INNER JOIN `teamster-332318`.`kipptaf_students`.`int_students__calendar_week` AS cw
    ON cw.academic_year = co.academic_year
    AND cw.schoolid = co.schoolid
    AND r.administered_at BETWEEN cw.week_start_monday AND cw.week_end_sunday
  GROUP BY r.student, r.assessment
),
dash_weeks AS (
  SELECT
    r.student,
    r.assessment,
    LOGICAL_OR(
      co.is_enrolled_week_end
      AND co.enroll_status IN (0, 2, 3)
      AND NOT co.is_out_of_district
    ) AS dash_ok
  FROM rollup_rows AS r
  INNER JOIN `teamster-332318`.`kipptaf_extracts`.`int_extracts__student_enrollments_weeks` AS co
    ON co.student_number = r.student_number
    AND co.academic_year = r.academic_year
    AND co.region = r.region
    AND r.administered_at BETWEEN co.week_start_monday AND co.week_end_sunday
  GROUP BY r.student, r.assessment
)
SELECT
  u.__row,
  CASE
    WHEN u.source_assessment_id IS NULL THEN 'C2'
    WHEN p.student IS NULL THEN 'UNEXPLAINED'
    WHEN w.student IS NULL THEN 'D1'
    WHEN NOT w.enrolled_week_end THEN 'D2'
    WHEN NOT w.status_ok THEN 'D3'
    WHEN NOT w.district_ok THEN 'D4'
    WHEN p.is_wpp THEN 'D5'
    WHEN p.is_untagged THEN 'D7'
    WHEN NOT w.grade_ok THEN 'D6'
    WHEN NOT COALESCE(dw.dash_ok, FALSE) THEN 'D9'
    ELSE 'UNEXPLAINED'
  END AS cause
FROM {unmatched} AS u
LEFT JOIN per_score AS p
  ON p.student = CAST(u.lea_student_identifier AS STRING)
  AND p.assessment = CAST(u.source_assessment_id AS STRING)
LEFT JOIN weeks AS w
  ON w.student = p.student
  AND w.assessment = p.assessment
LEFT JOIN dash_weeks AS dw
  ON dw.student = p.student
  AND dw.assessment = p.assessment

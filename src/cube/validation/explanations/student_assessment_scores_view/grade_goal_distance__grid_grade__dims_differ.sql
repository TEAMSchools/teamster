-- trunk-ignore-all(sqlfluff)
-- fmt: off
-- cause C11 = cube: the student changed grade or school during the year; Cube takes grade and school from the enrollment stint the score's section enrollment attaches to, the dashboard from the stint that covers the assessment week
-- saved e6efa320ce822616336460562477fd4c3a6b8de07f78fc43ea60136351c462c6

WITH score_year AS (
  SELECT
    CAST(student_number AS STRING) AS student,
    CAST(assessment_id AS STRING) AS assessment,
    MIN(academic_year) AS academic_year
  FROM `teamster-332318`.`kipptaf_assessments`.`int_assessments__response_rollup`
  WHERE academic_year >= 2025
  GROUP BY student, assessment
),
moved AS (
  SELECT
    CAST(student_number AS STRING) AS student,
    academic_year,
    COUNT(DISTINCT CONCAT(CAST(schoolid AS STRING), '/', CAST(grade_level AS STRING))) > 1 AS has_two_stints
  FROM `teamster-332318`.`kipptaf_extracts`.`int_extracts__student_enrollments`
  WHERE academic_year >= 2025
  GROUP BY student, academic_year
)
SELECT
  u.__row,
  CASE
    WHEN m.has_two_stints THEN 'C11'
    ELSE 'UNEXPLAINED'
  END AS cause
FROM {unmatched} AS u
LEFT JOIN score_year AS sy
  ON sy.student = CAST(u.lea_student_identifier AS STRING)
  AND sy.assessment = CAST(u.source_assessment_id AS STRING)
LEFT JOIN moved AS m
  ON m.student = sy.student
  AND m.academic_year = sy.academic_year

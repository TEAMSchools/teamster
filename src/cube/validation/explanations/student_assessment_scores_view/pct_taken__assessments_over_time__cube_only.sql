-- trunk-ignore-all(sqlfluff)
-- fmt: off
-- cause C2 = dashboard: the dashboard reads only Illuminate and Focus assessments; Cube's view also holds i-Ready, DIBELS, STAR and state test scores
-- cause D8 = dashboard: the assessment's administered date falls in a later academic year than its own academic_year, so Cube files the score under the administered date's year while the dashboard keeps the assessment's year and the sheet's year filter drops it
-- unchanged C2 since 1b9b6ea744c8c4f18d7504ea2c8e57959cdf1d90bd57873ee968d1d56eb47927
-- saved 4b10ebd5fc370fa4ee7a92f8c0edd7234ea2f16760df8d21b22d5cd040f84a04

WITH per_score AS (
  SELECT
    CAST(student_number AS STRING) AS student,
    CAST(assessment_id AS STRING) AS assessment,
    LOGICAL_OR(
      academic_year
      < EXTRACT(YEAR FROM administered_at) - IF(EXTRACT(MONTH FROM administered_at) < 7, 1, 0)
    ) AS later_administered_year
  FROM `teamster-332318`.`kipptaf_assessments`.`int_assessments__response_rollup`
  WHERE academic_year >= 2025
  GROUP BY student, assessment
)
SELECT
  u.__row,
  CASE
    WHEN u.source_assessment_id IS NULL THEN 'C2'
    WHEN p.later_administered_year THEN 'D8'
    ELSE 'UNEXPLAINED'
  END AS cause
FROM {unmatched} AS u
LEFT JOIN per_score AS p
  ON p.student = CAST(u.lea_student_identifier AS STRING)
  AND p.assessment = CAST(u.source_assessment_id AS STRING)

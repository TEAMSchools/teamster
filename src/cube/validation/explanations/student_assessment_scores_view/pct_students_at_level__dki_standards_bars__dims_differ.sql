-- trunk-ignore-all(sqlfluff)
-- fmt: off
-- cause C10 = dashboard: the dashboard groups band numbers into 3 levels by fixed numbers (ES/MS 1-2 Below, 3 Approaching, 4-5 At/Above; HS 1 Below, 2 Approaching, 3-5 At/Above; other numbers stay as themselves); Cube sets mastery_level relative to each band set's mastery band

WITH bands AS (
  SELECT
    CAST(rr.student_number AS STRING) AS student,
    CAST(rr.assessment_id AS STRING) AS assessment,
    rr.response_type_code,
    rr.student_number,
    rr.academic_year,
    ANY_VALUE(rr.performance_band_label_number) AS band
  FROM `teamster-332318`.`kipptaf_assessments`.`int_assessments__response_rollup` AS rr
  WHERE rr.academic_year >= 2025
  GROUP BY student, assessment, rr.response_type_code, rr.student_number, rr.academic_year
),
levels AS (
  SELECT
    b.student,
    b.assessment,
    b.response_type_code,
    b.band,
    LOGICAL_OR(co.school_level = 'HS') AS is_hs
  FROM bands AS b
  INNER JOIN `teamster-332318`.`kipptaf_extracts`.`int_extracts__student_enrollments` AS co
    ON co.student_number = b.student_number
    AND co.academic_year = b.academic_year
  GROUP BY b.student, b.assessment, b.response_type_code, b.band
),
dashboard_level AS (
  SELECT
    student,
    assessment,
    response_type_code,
    COALESCE(
      CASE
        WHEN is_hs AND band = 1 THEN 'Below'
        WHEN is_hs AND band = 2 THEN 'Approaching'
        WHEN is_hs AND band IN (3, 4, 5) THEN 'At/Above'
        WHEN NOT is_hs AND band IN (1, 2) THEN 'Below'
        WHEN NOT is_hs AND band = 3 THEN 'Approaching'
        WHEN NOT is_hs AND band IN (4, 5) THEN 'At/Above'
      END,
      CAST(band AS STRING)
    ) AS level
  FROM levels
)
SELECT
  u.__row,
  CASE
    WHEN d.student IS NULL THEN 'UNEXPLAINED'
    WHEN d.level IS DISTINCT FROM u.mastery_level THEN 'C10'
    ELSE 'UNEXPLAINED'
  END AS cause
FROM {unmatched} AS u
LEFT JOIN dashboard_level AS d
  ON d.student = CAST(u.lea_student_identifier AS STRING)
  AND d.assessment = CAST(u.source_assessment_id AS STRING)
  AND d.response_type_code IS NOT DISTINCT FROM u.response_type_code

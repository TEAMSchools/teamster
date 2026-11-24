-- trunk-ignore-all(sqlfluff)
-- fmt: off
-- cause C3 = cube: Cube keeps only internal assessments (where rr.is_internal_assessment)
-- cause C6 = cube: Cube keeps a score only when it resolves to a section enrollment (inner join to int_assessments__resolved_section_enrollments); the dashboard needs only the student's year enrollment
-- cause C7 = cube: the score's section enrollment attaches to no school enrollment stint (its student_enrollment_key is null or matches no dim_student_enrollments row), so Cube reaches no student or school and its school access filter drops the score
-- unchanged C3 since 2e047da162dc7df95edd6ab3d931bf233c5957ca5cf7b2e736b0348882e77a0b
-- unchanged C6 since 2e047da162dc7df95edd6ab3d931bf233c5957ca5cf7b2e736b0348882e77a0b
-- saved 44d713f124db4b75a97079f863455ac1cf0aa5743dfafb12e3dd36d430fe597f

WITH chain AS (
  SELECT
    CAST(rr.student_number AS STRING) AS student,
    CAST(rr.assessment_id AS STRING) AS assessment,
    LOGICAL_OR(rr.is_internal_assessment) AS is_internal,
    LOGICAL_OR(sr.student_number IS NOT NULL) AS has_section,
    LOGICAL_AND(IF(sr.student_number IS NULL, NULL, se.student_enrollment_key IS NULL)) AS no_stint
  FROM `teamster-332318`.`kipptaf_assessments`.`int_assessments__response_rollup` AS rr
  LEFT JOIN `teamster-332318`.`kipptaf_assessments`.`int_assessments__resolved_section_enrollments` AS sr
    ON rr.student_number = sr.student_number
    AND rr.source = sr.source
    AND rr.assessment_id = sr.canonical_assessment_id
    AND rr._dbt_source_project = sr._dbt_source_project
    AND sr.source_type = 'internal'
  LEFT JOIN `teamster-332318`.`kipptaf_marts`.`dim_student_section_enrollments` AS sse
    ON sse.student_section_enrollment_key = sr.student_section_enrollment_key
  LEFT JOIN `teamster-332318`.`kipptaf_marts`.`dim_student_enrollments` AS se
    ON se.student_enrollment_key = sse.student_enrollment_key
  WHERE rr.academic_year >= 2025
  GROUP BY student, assessment
)
SELECT
  u.__row,
  CASE
    WHEN ch.student IS NULL THEN 'UNEXPLAINED'
    WHEN NOT ch.is_internal THEN 'C3'
    WHEN NOT ch.has_section THEN 'C6'
    WHEN ch.no_stint THEN 'C7'
    ELSE 'UNEXPLAINED'
  END AS cause
FROM {unmatched} AS u
LEFT JOIN chain AS ch
  ON ch.student = CAST(u.lea_student_identifier AS STRING)
  AND ch.assessment = CAST(u.source_assessment_id AS STRING)

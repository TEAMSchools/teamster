-- trunk-ignore-all(sqlfluff)
-- fmt: off
-- cause C1 = dashboard: the dashboard model keeps only the current and prior academic year
-- cause C2 = dashboard: the dashboard reads only Illuminate and Focus assessments; Cube's view also holds i-Ready, DIBELS, STAR and state test scores

SELECT
  u.__row,
  CASE
    WHEN CAST(u.academic_year AS INT64) < 2025 THEN 'C1'
    WHEN u.source_assessment_id IS NULL THEN 'C2'
    ELSE 'UNEXPLAINED'
  END AS cause
FROM {unmatched} AS u

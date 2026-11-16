-- trunk-ignore-all(sqlfluff)
-- fmt: off
-- cause C2 = dashboard: the dashboard reads only Illuminate and Focus assessments; Cube's view also holds i-Ready, DIBELS, STAR and state test scores

SELECT
  u.__row,
  CASE
    WHEN u.source_assessment_id IS NULL THEN 'C2'
    ELSE 'UNEXPLAINED'
  END AS cause
FROM {unmatched} AS u

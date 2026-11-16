-- trunk-ignore-all(sqlfluff)
-- fmt: off
-- cause C7 = cube: Cube files a never-sat assessment as response type not_taken (coalesce(rr.response_type, 'not_taken')); the dashboard leaves it blank

SELECT
  u.__row,
  CASE
    WHEN u.response_type = 'not_taken' THEN 'C7'
    ELSE 'UNEXPLAINED'
  END AS cause
FROM {unmatched} AS u

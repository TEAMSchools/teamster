SELECT
  n,
  n + 1 AS n2,
  n + 2 AS n3,
  n + 3 AS n4,
  n + 4 AS n5
FROM
  utilities.row_generator_smallint
WHERE
  n <= 5

select n, n + 1 as n2, n + 2 as n3, n + 3 as n4, n + 4 as n5
from utilities.row_generator_smallint
where n <= 5

select
    * except (_dagster_partition_school_year, date_of_birth, grade_level),

    _dagster_partition_school_year as enrollment_school_year,

    parse_date('%m%d%y', date_of_birth) as date_of_birth,

    case
        grade_level when '4' then 9 when '5' then 10 when '6' then 11 when '7' then 12
    end as grade_level,
from {{ source("collegeboard", "src_collegeboard__ap") }}

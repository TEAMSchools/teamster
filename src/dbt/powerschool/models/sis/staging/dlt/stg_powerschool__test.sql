select
    `name`,
    `description`,
    psguid,
    importcode,

    cast(dcid as int) as dcid,
    cast(id as int) as id,
    cast(test_type as int) as test_type,
    cast(alpha_entry_type as int) as alpha_entry_type,
    cast(historical_test as int) as historical_test,
    cast(number_entry_type as int) as number_entry_type,
    cast(percent_entry_type as int) as percent_entry_type,
    cast(teacher_access as int) as teacher_access,
from {{ source("powerschool_dlt", "test") }}

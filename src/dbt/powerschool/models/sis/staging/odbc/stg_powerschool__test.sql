select
    * except (
        dcid,
        id,
        test_type,
        alpha_entry_type,
        historical_test,
        number_entry_type,
        percent_entry_type,
        teacher_access
    ),

    /* column transformations */
    dcid.int_value as dcid,
    id.int_value as id,
    test_type.int_value as test_type,
    alpha_entry_type.int_value as alpha_entry_type,
    historical_test.int_value as historical_test,
    number_entry_type.int_value as number_entry_type,
    percent_entry_type.int_value as percent_entry_type,
    teacher_access.int_value as teacher_access,
from {{ source("powerschool_odbc", "src_powerschool__test") }}

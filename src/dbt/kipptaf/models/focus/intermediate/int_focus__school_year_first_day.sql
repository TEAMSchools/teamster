select *, from {{ source("kippmiami_focus", "int_focus__school_year_first_day") }}

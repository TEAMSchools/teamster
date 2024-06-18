select region, academic_year, `quarter`, week_number, storecode_type, expectation,
from
    {{ source("reporting", "src_reporting__gradebook_expectations") }}
    unpivot (expectation for storecode_type in (`W`, `F`, `S`))

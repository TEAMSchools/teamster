select *, from {{ source("assessments", "src_assessments__qbls_power_standards") }}

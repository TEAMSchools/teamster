select * from {{ source("assessments", "src_assessments__standard_domains") }}

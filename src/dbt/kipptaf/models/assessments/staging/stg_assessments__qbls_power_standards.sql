select
    region,
    academic_year,
    term_name,
    grade_level,
    illuminate_subject_area,
    parent_standard,
    standard_code,
    is_power_standard,
    qbl,
from {{ source("assessments", "src_assessments__qbls_power_standards") }}

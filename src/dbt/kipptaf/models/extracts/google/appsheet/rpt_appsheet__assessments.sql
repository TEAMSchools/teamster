select * except (regions_assessed_array), from {{ ref("int_assessments__assessments") }}

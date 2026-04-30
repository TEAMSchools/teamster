select
    *,

    grade_level + 1 as illuminate_grade_level_id,

    concat(module_type, module_sequence) as module_code,

    array(
        select distinct trim(r),
        from unnest(split(regions_assessed, ',')) as r
        where trim(r) != ''
    ) as regions_assessed_array,
from
    {{
        source(
            "google_appsheet", "src_google_appsheet__illuminate_assessments_extension"
        )
    }}

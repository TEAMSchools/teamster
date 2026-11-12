with
    source as (
        select
            *,

            split(regexp_replace(regions_assessed, r'\s+', ''), ',') as regions_split,
        from
            {{
                source(
                    "google_appsheet",
                    "src_google_appsheet__illuminate_assessments_extension",
                )
            }}
    )

select
    * except (regions_split),

    grade_level + 1 as illuminate_grade_level_id,

    concat(module_type, module_sequence) as module_code,

    array(
        select distinct r, from unnest(regions_split) as r where r != '' order by r
    ) as regions_assessed_array,
from source

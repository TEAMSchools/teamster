select
    a.*,

    ias.module_type,
    if(ias.module_type is not null, true, false) as is_internal_assessment,

    regexp_replace(
        coalesce(
            regexp_extract(a.title, ias.module_number_pattern_1 || r'\s?\d+'),
            regexp_extract(a.title, ias.module_number_pattern_2 || r'\s?\d+')
        ),
        r'\s',
        ''
    ) as module_number,
from {{ ref("base_illuminate__assessments") }} as a
left join
    {{ source("assessments", "src_assessments__internal_assessment_scopes") }} as ias
    on a.scope = ias.scope
    and a.academic_year_clean = ias.academic_year

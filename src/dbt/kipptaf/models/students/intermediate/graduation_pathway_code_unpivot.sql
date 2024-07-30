select
    _dbt_source_relation,
    studentsdcid,
    values_column as code,
    case
        regexp_extract(name_column, r'_([a-z]+)$')
        when 'ela'
        then 'ELA'
        when 'math'
        then 'Math'
    end as discipline,
from
    {{ ref("stg_powerschool__s_nj_stu_x") }} unpivot (
        values_column for name_column
        in (graduation_pathway_ela, graduation_pathway_math)
    )

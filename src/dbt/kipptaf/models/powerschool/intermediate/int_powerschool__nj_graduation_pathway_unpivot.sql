select
    _dbt_source_relation,
    studentsdcid,
    values_column,
    regexp_extract(name_column, r'_([a-z]+)$') as subject,
    if(values_column = 'N', true, false) as is_portfolio_eligible,
    if(values_column = 'M', true, false) as is_iep_eligible,
    if(values_column in ('M', 'N'), true, false) as met_requirement,
from
    {{ ref("stg_powerschool__s_nj_stu_x") }} unpivot (
        values_column for name_column
        in (graduation_pathway_ela, graduation_pathway_math)
    )

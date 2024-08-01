select
    _dbt_source_relation,
    studentsdcid,
    name_column,
    values_column,

    case
        when name_column in ('graduation_pathway_ela', 'state_assessment_name')
        then 'ELA'
        when name_column in ('graduation_pathway_math', 'math_state_assessment_name')
        then 'Math'
    end as discipline,
from
    {{ ref("stg_powerschool__s_nj_stu_x") }} unpivot (
        values_column for name_column in (
            graduation_pathway_ela,
            graduation_pathway_math,
            math_state_assessment_name,
            state_assessment_name
        )
    )

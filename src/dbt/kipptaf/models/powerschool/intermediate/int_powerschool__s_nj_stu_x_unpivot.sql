select
    _dbt_source_relation,
    studentsdcid,
    name_column,
    values_column,

    if(values_column = 'N', true, false) as is_portfolio_eligible,
    if(values_column = 'M', true, false) as is_iep_eligible,
    if(values_column in ('M', 'N'), true, false) as met_requirement,

    case
        when name_column in ('graduation_pathway_ela', 'graduation_pathway_math')
        then 'Graduation Pathway'
        when name_column in ('state_assessment_name', 'math_state_assessment_name')
        then 'State Assessment Name'
    end as value_type,

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

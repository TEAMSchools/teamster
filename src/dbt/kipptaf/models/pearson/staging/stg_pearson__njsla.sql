with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_pearson", "stg_pearson__njsla"),
                    source("kippcamden_pearson", "stg_pearson__njsla"),
                    source("kipppaterson_pearson", "int_pearson__njsla"),
                ]
            )
        }}
    )

select
    *,

    if(
        `subject` = 'English Language Arts/Literacy', 'English Language Arts', `subject`
    ) as subject_area,

    if(`period` = 'FallBlock', 'Fall', `period`) as administration_period,

    {{ extract_source_project("union_relations") }} as _dbt_source_project,

    case
        testcode
        when 'SC05'
        then 'SCI05'
        when 'SC08'
        then 'SCI08'
        when 'SC11'
        then 'SCI11'
        else testcode
    end as module_code,

from union_relations

with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", model.name),
                    source("kippcamden_powerschool", model.name),
                    source("kippmiami_powerschool", model.name),
                ]
            )
        }}
    )

select
    ur.*,

    {{ extract_source_project("ur") }} as _dbt_source_project,

    case
        when ur.cumulative_y1_gpa_unweighted >= 3.00
        then 4
        when ur.cumulative_y1_gpa_unweighted >= 2.50
        then 3
        when ur.cumulative_y1_gpa_unweighted >= 2.00
        then 2
        when ur.cumulative_y1_gpa_unweighted < 2.00
        then 1
    end as cumulative_y1_gpa_unweighted_band,

    case
        when ur.cumulative_y1_gpa_projected_unweighted >= 3.00
        then 4
        when ur.cumulative_y1_gpa_projected_unweighted >= 2.50
        then 3
        when ur.cumulative_y1_gpa_projected_unweighted >= 2.00
        then 2
        when ur.cumulative_y1_gpa_projected_unweighted < 2.00
        then 1
    end as cumulative_y1_gpa_projected_unweighted_band,

from union_relations as ur

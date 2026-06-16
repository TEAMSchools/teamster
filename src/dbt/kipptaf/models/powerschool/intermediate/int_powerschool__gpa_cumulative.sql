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

-- trunk-ignore(sqlfluff/AM04)
select
    ur.*,

    regexp_extract(ur._dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,

    case
        when cumulative_y1_gpa_unweighted >= 3.00
        then 4
        when cumulative_y1_gpa_unweighted >= 2.50
        then 3
        when cumulative_y1_gpa_unweighted >= 2.00
        then 2
        when cumulative_y1_gpa_unweighted < 2.00
        then 1
    end as cumulative_y1_gpa_unweighted_band,

    case
        when cumulative_y1_gpa_projected_unweighted >= 3.00
        then 4
        when cumulative_y1_gpa_projected_unweighted >= 2.50
        then 3
        when cumulative_y1_gpa_projected_unweighted >= 2.00
        then 2
        when cumulative_y1_gpa_projected_unweighted < 2.00
        then 1
    end as cumulative_y1_gpa_projected_unweighted_band,

from union_relations as ur

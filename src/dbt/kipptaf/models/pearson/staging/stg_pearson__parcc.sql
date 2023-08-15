with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_pearson", model.name),
                    source("kippcamden_pearson", model.name),
                ]
            )
        }}
    )

select *, safe_cast(left(assessment_year, 4) as int) as academic_year,
from union_relations

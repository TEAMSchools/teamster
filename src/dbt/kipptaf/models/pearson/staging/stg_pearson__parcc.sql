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

select
    * except (shipreportschoolcode, shipreportdistrictcode, statefield9),
    safe_cast(left(assessmentyear, 4) as int) as academic_year,
    coalesce(
        shipreportschoolcode.long_value,
        safe_cast(shipreportschoolcode.float_value as int)
    ) as shipreportschoolcode,
    coalesce(
        shipreportdistrictcode.long_value,
        safe_cast(shipreportdistrictcode.float_value as int)
    ) as shipreportdistrictcode,
    coalesce(
        statefield9.string_value, safe_cast(statefield9.double_value as string)
    ) as statefield9,
from union_relations

with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "stg_powerschool__terms"),
                    source("kippcamden_powerschool", "stg_powerschool__terms"),
                    source("kipppaterson_powerschool", "stg_powerschool__terms"),
                ]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
select
    *,

    {{ extract_source_project() }} as _dbt_source_project,

    -- Picks one row per school/year/abbreviation where the raw terms table
    -- holds a duplicate. No such duplicate exists today, so this is defensive
    -- only.
    row_number() over (
        partition by schoolid, yearid, abbreviation, {{ extract_source_project() }}
        order by id
    ) as rn,
from union_relations

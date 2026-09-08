with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "stg_powerschool__terms"),
                    source("kippcamden_powerschool", "stg_powerschool__terms"),
                    source("kippmiami_powerschool", "stg_powerschool__terms"),
                    source("kipppaterson_powerschool", "stg_powerschool__terms"),
                ]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
select
    *,

    {{ extract_source_project() }} as _dbt_source_project,

    -- Guards a quarter-grain join against a duplicate raw record for the same
    -- school/year/term, so consumers attaching termbins columns see one row
    -- per quarter. No such duplicate exists today -- all 2,139 keys across the
    -- four districts are singletons -- so this is defensive only.
    row_number() over (
        partition by schoolid, yearid, abbreviation, {{ extract_source_project() }}
        order by id
    ) as rn,
from union_relations

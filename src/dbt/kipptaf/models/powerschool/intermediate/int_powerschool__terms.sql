-- Miami is absent from this list. Focus does not supply Miami quarters for
-- every school before AY2025, and the archive's quarters overlap the Focus ones
-- with different dates, so wiring Miami in needs a precedence rule (#5397).
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "int_powerschool__terms"),
                    source("kippcamden_powerschool", "int_powerschool__terms"),
                    source("kipppaterson_powerschool", "int_powerschool__terms"),
                ]
            )
        }}
    )

select ur.*, {{ extract_source_project("ur") }} as _dbt_source_project,

from union_relations as ur

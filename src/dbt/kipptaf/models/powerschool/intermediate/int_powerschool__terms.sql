-- Miami is absent from this list on purpose: the Focus branch of
-- int_students__terms floors at syear 2018, so Focus already supplies Miami
-- terms across the whole PowerSchool archive range (#4750).
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

{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "int_powerschool__calendar_rollup"),
            source("kippcamden_powerschool", "int_powerschool__calendar_rollup"),
            source("kippmiami_powerschool", "int_powerschool__calendar_rollup"),
            source("kipppaterson_powerschool", "int_powerschool__calendar_rollup"),
        ]
    )
}}

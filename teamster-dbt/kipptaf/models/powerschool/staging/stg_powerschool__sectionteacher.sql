{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__sectionteacher"),
            source("kippcamden_powerschool", "stg_powerschool__sectionteacher"),
            source("kippmiami_powerschool", "stg_powerschool__sectionteacher"),
        ]
    )
}}

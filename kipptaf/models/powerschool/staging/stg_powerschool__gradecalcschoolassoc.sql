{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__gradecalcschoolassoc"),
            source("kippcamden_powerschool", "stg_powerschool__gradecalcschoolassoc"),
            source("kippmiami_powerschool", "stg_powerschool__gradecalcschoolassoc"),
        ]
    )
}}

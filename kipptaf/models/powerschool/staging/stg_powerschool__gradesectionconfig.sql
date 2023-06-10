{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__gradesectionconfig"),
            source("kippcamden_powerschool", "stg_powerschool__gradesectionconfig"),
            source("kippmiami_powerschool", "stg_powerschool__gradesectionconfig"),
        ]
    )
}}

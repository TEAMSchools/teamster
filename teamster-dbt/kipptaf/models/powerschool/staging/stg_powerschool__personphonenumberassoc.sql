{{
    dbt_utils.union_relations(
        relations=[
            source(
                "kippnewark_powerschool", "stg_powerschool__personphonenumberassoc"
            ),
            source(
                "kippcamden_powerschool", "stg_powerschool__personphonenumberassoc"
            ),
            source(
                "kippmiami_powerschool", "stg_powerschool__personphonenumberassoc"
            ),
        ]
    )
}}

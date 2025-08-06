{{
    dbt_utils.union_relations(
        relations=[
            source(
                "kippnewark_powerschool", "stg_powerschool__gpprogresssubjectenrolled"
            ),
            source(
                "kippcamden_powerschool", "stg_powerschool__gpprogresssubjectenrolled"
            ),
        ]
    )
}}

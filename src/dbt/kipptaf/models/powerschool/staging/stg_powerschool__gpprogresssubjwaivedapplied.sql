{{
    dbt_utils.union_relations(
        relations=[
            source(
                "kippnewark_powerschool",
                "stg_powerschool__gpprogresssubjwaivedapplied",
            ),
            source(
                "kippcamden_powerschool",
                "stg_powerschool__gpprogresssubjwaivedapplied",
            ),
        ]
    )
}}

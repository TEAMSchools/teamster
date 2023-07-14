{{
    dbt_utils.union_relations(
        relations=[
            source(
                "kippnewark_powerschool", "stg_powerschool__assignmentcategoryassoc"
            ),
            source(
                "kippcamden_powerschool", "stg_powerschool__assignmentcategoryassoc"
            ),
            source(
                "kippmiami_powerschool", "stg_powerschool__assignmentcategoryassoc"
            ),
        ]
    )
}}

{{
    dbt_utils.union_relations(
        relations=[
            source(
                "kippnewark_powerschool", "stg_powerschool__gradecalcformulaweight"
            ),
            source(
                "kippcamden_powerschool", "stg_powerschool__gradecalcformulaweight"
            ),
            source(
                "kippmiami_powerschool", "stg_powerschool__gradecalcformulaweight"
            ),
        ]
    )
}}

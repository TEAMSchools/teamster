{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__gradeformulaset"),
            source("kippcamden_powerschool", "stg_powerschool__gradeformulaset"),
            source("kippmiami_powerschool", "stg_powerschool__gradeformulaset"),
        ]
    )
}}

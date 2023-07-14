{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "int_powerschool__district_entry_date"),
            source("kippcamden_powerschool", "int_powerschool__district_entry_date"),
            source("kippmiami_powerschool", "int_powerschool__district_entry_date"),
        ]
    )
}}

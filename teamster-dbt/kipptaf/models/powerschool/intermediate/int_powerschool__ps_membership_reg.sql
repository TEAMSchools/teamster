{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "int_powerschool__ps_membership_reg"),
            source("kippcamden_powerschool", "int_powerschool__ps_membership_reg"),
            source("kippmiami_powerschool", "int_powerschool__ps_membership_reg"),
        ]
    )
}}

{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "int_powerschool__ps_adaadm_daily_ctod"),
            source("kippcamden_powerschool", "int_powerschool__ps_adaadm_daily_ctod"),
            source("kippmiami_powerschool", "int_powerschool__ps_adaadm_daily_ctod"),
        ]
    )
}}

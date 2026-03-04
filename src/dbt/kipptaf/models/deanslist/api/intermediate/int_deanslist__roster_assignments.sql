{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_deanslist", "int_deanslist__roster_assignments"),
            source("kippcamden_deanslist", "int_deanslist__roster_assignments"),
            source("kippmiami_deanslist", "int_deanslist__roster_assignments"),
        ]
    )
}}

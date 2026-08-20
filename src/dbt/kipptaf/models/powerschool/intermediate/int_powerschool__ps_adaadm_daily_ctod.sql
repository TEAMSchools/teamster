-- Thin PowerSchool union only. Every derived flag, anchor, and running calc that
-- used to live here moved to int_students__attendance_daily, so there is one
-- definition over the SIS-neutral union rather than one per branch. The window
-- partitions were already scoped by _dbt_source_project, so computing them
-- post-union is arithmetically identical.
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool",
                        "int_powerschool__ps_adaadm_daily_ctod",
                    ),
                    source(
                        "kippcamden_powerschool",
                        "int_powerschool__ps_adaadm_daily_ctod",
                    ),
                    source(
                        "kippmiami_powerschool",
                        "int_powerschool__ps_adaadm_daily_ctod",
                    ),
                    source(
                        "kipppaterson_powerschool",
                        "int_powerschool__ps_adaadm_daily_ctod",
                    ),
                ]
            )
        }}
    )

select *, {{ extract_source_project("union_relations") }} as _dbt_source_project,
from union_relations

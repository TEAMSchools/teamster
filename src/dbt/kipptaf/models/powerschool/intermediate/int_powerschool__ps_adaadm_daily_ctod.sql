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
    ),

    -- Miami's student_number is the 8400-prefixed Focus id since #5148 and the
    -- frozen archive carries the bare PowerSchool number. Renumbered here, where
    -- the archive first enters kipptaf, so every consumer reads one id space.
    unioned as (
        select ur.*, {{ extract_source_project("ur") }} as _dbt_source_project,
        from union_relations as ur
    )

select
    * except (student_number),

    {{ focus_student_number("student_number", "yearid + 1990", "_dbt_source_project") }}
    as student_number,
from unioned

-- All four regions are unioned here, matching
-- int_finalsite__student_address_of_record. Focus is the Miami consumer and the
-- NJ regions carry no Focus student id, so the `rpt_focus__*` filter on
-- `focus_student_id_prefixed` keeps their rows out of the Focus feeds.
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippcamden_finalsite",
                        "int_finalsite__contact_address_of_record",
                    ),
                    source(
                        "kippmiami_finalsite",
                        "int_finalsite__contact_address_of_record",
                    ),
                    source(
                        "kippnewark_finalsite",
                        "int_finalsite__contact_address_of_record",
                    ),
                    source(
                        "kipppaterson_finalsite",
                        "int_finalsite__contact_address_of_record",
                    ),
                ]
            )
        }}
    )

select *, {{ extract_source_project("union_relations") }} as _dbt_source_project,
from union_relations

-- Union of the per-region Finalsite int_finalsite__student_contacts models
-- (grain: finalsite_enrollment_id x contact_slot) — the source for the network
-- contact surface. Union a region here only when it cuts over to Finalsite
-- contacts reporting (today the NJ regions: Newark, Camden, Paterson); its rows
-- flow straight into int_students__contacts' Finalsite branch, so a
-- not-yet-cutover region (e.g. Miami, still PowerSchool-sourced for contacts)
-- must NOT be added here even though its api layer is enabled.
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippcamden_finalsite", "int_finalsite__student_contacts"),
                    source("kippnewark_finalsite", "int_finalsite__student_contacts"),
                    source(
                        "kipppaterson_finalsite", "int_finalsite__student_contacts"
                    ),
                ]
            )
        }}
    )

select *, {{ extract_code_location("union_relations") }} as _dbt_source_project,
from union_relations

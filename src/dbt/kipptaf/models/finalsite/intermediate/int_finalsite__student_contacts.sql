-- Add a region below only when it cuts over to Finalsite contacts reporting.
-- These rows flow straight into int_students__contacts' Finalsite branch, so a
-- region that is still PowerSchool-sourced for contacts double-counts there.
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

select *, {{ extract_source_project("union_relations") }} as _dbt_source_project,
from union_relations

-- Add a region below once its Finalsite API layer is wired.
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippcamden_finalsite", "int_finalsite__contact_id_attributes"
                    ),
                    source(
                        "kippmiami_finalsite", "int_finalsite__contact_id_attributes"
                    ),
                    source(
                        "kippnewark_finalsite", "int_finalsite__contact_id_attributes"
                    ),
                    source(
                        "kipppaterson_finalsite",
                        "int_finalsite__contact_id_attributes",
                    ),
                ]
            )
        }}
    )

select *, {{ extract_source_project("union_relations") }} as _dbt_source_project,
from union_relations

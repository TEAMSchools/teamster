-- Finalsite contacts API layer is enabled only in regions with Finalsite
-- ingestion wired (today: KIPP Miami and KIPP Newark). Add each region's
-- relation here when its api layer is enabled.
--
-- focus_student_id_prefixed (the 8400-prefixed Focus student id consumed by the
-- rpt_focus__* extracts) is produced by the package model and flows through the
-- union below; it is null for non-Focus regions (e.g. Newark), so the
-- rpt_focus__* consumers that filter `focus_student_id_prefixed is not null`
-- see only their own region's rows.
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippmiami_finalsite", "int_finalsite__contact_id_attributes"
                    ),
                    source(
                        "kippnewark_finalsite", "int_finalsite__contact_id_attributes"
                    ),
                ]
            )
        }}
    )

select *, {{ extract_code_location("union_relations") }} as _dbt_source_project,
from union_relations

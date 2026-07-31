-- Finalsite contacts API layer is enabled only in regions with Finalsite
-- ingestion wired (today: KIPP Miami). Add each region's relation here when its
-- api layer is enabled.
--
-- The package model's output schema changed in this PR (is_transfer_out
-- replaces lifecycle_action, withdrawal_reason etc.). This union wrapper reads
-- the district source via compile-time union_relations, so this comment forces
-- state:modified — CI rebuilds it against the reseeded zz_stg copy that carries
-- the new columns.
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippmiami_finalsite", "int_finalsite__enrollment_lifecycle"
                    ),
                ]
            )
        }}
    )

select *, {{ extract_source_project("union_relations") }} as _dbt_source_project,
from union_relations

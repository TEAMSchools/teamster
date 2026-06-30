-- Finalsite contacts API layer is enabled only in regions with Finalsite
-- ingestion wired (today: KIPP Miami). Add each region's relation here when its
-- api layer is enabled.
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippmiami_finalsite", "int_finalsite__contact_id_attributes"
                    ),
                ]
            )
        }}
    )

select
    *,

    -- Focus stores student_id as the FLDOE district number (8400) prefixed to
    -- the Finalsite-minted id; this prefixed value equals Focus
    -- `students.student_id` directly and is what every Focus extract emits.
    -- Derived here at the kipptaf wrapper (not the package model) so a new
    -- column surfaces in CI without waiting on a district prod rebuild —
    -- `dbt_utils.union_relations` is compile-time.
    concat('8400', focus_student_id) as focus_student_id_prefixed,
    {{ extract_code_location("union_relations") }} as _dbt_source_project,
from union_relations

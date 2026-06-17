-- LINKED_STUDENTS pairs sibling enrollments by Focus STDT_ID. STDT_ID is null
-- until the Finalsite-minted id lands in id_attributes, so no links are emitted
-- yet (this returns no rows). When the id source exists, inner join
-- int_finalsite__contact_id_attributes on rel.finalsite_enrollment_id and
-- rel.rel_id and project least/greatest of the two student ids.
select
    cast(null as string) as primary_student_id,
    cast(null as string) as secondary_student_id,
    'sibling' as relationship,
from {{ ref("stg_finalsite__contact_relationships") }} as rel
where rel.rel_type = 'sibling' and false

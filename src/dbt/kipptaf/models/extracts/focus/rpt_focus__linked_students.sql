-- grain projection to the unordered sibling pair: least/greatest normalize each
-- bidirectional edge (a->b and b->a) to one (primary, secondary) tuple, which
-- distinct collapses; not a mask for upstream duplicates.
select distinct
    least(
        ida_a.focus_student_id_prefixed, ida_b.focus_student_id_prefixed
    ) as primary_student_id,
    greatest(
        ida_a.focus_student_id_prefixed, ida_b.focus_student_id_prefixed
    ) as secondary_student_id,
from {{ ref("stg_finalsite__contact_relationships") }} as rel
inner join
    {{ ref("int_finalsite__contact_id_attributes") }} as ida_a
    on rel.finalsite_enrollment_id = ida_a.finalsite_enrollment_id
    and ida_a.focus_student_id is not null
inner join
    {{ ref("int_finalsite__contact_id_attributes") }} as ida_b
    on rel.rel_id = ida_b.finalsite_enrollment_id
    and ida_b.focus_student_id is not null
where rel.rel_type = 'sibling'

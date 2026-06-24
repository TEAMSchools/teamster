with
    sibling_pairs as (
        select
            ida_a.focus_student_id as student_id_a,
            ida_b.focus_student_id as student_id_b,
        from {{ ref("stg_finalsite__contact_relationships") }} as rel
        inner join
            {{ ref("int_finalsite__enrollment_lifecycle") }} as la
            on rel.finalsite_enrollment_id = la.finalsite_enrollment_id
        inner join
            {{ ref("int_finalsite__enrollment_lifecycle") }} as lb
            on rel.rel_id = lb.finalsite_enrollment_id
        inner join
            {{ ref("int_finalsite__contact_id_attributes") }} as ida_a
            on rel.finalsite_enrollment_id = ida_a.finalsite_enrollment_id
        inner join
            {{ ref("int_finalsite__contact_id_attributes") }} as ida_b
            on rel.rel_id = ida_b.finalsite_enrollment_id
        where
            rel.rel_type = 'sibling'
            and ida_a.focus_student_id is not null
            and ida_b.focus_student_id is not null
    )

-- grain projection to the unordered sibling pair: least/greatest normalize each
-- bidirectional edge (a->b and b->a) to the same (primary, secondary) tuple, so
-- distinct collapses them; every column is determined by the pair, not a mask
-- for upstream duplicates.
-- trunk-ignore(sqlfluff/ST06): column order fixed by Focus LINKED_STUDENTS contract
select distinct
    least(student_id_a, student_id_b) as primary_student_id,
    greatest(student_id_a, student_id_b) as secondary_student_id,

    'sibling' as relationship,
from sibling_pairs

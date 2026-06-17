with
    sibling_edges as (
        select rel.finalsite_enrollment_id, rel.rel_id,
        from {{ ref("stg_finalsite__contact_relationships") }} as rel
        where rel.rel_type = 'sibling'
    ),

    student_ids as (
        select
            c.finalsite_enrollment_id,
            (
                select av.value.string_value,
                from unnest(c.id_attributes) as av
                where av.field_name = '{{ var("finalsite_focus_student_id_field") }}'
                order by av.field_id
                limit 1
            ) as stdt_id,
        from {{ ref("stg_finalsite__contacts") }} as c
        inner join
            {{ ref("int_finalsite__enrollment_lifecycle") }} as l
            on c.finalsite_enrollment_id = l.finalsite_enrollment_id
    ),

    pairs as (
        select pri.stdt_id as id_a, sec.stdt_id as id_b,
        from sibling_edges as e
        inner join
            student_ids as pri
            on e.finalsite_enrollment_id = pri.finalsite_enrollment_id
        inner join student_ids as sec on e.rel_id = sec.finalsite_enrollment_id
        where pri.stdt_id is not null and sec.stdt_id is not null
    )

-- trunk-ignore(sqlfluff/ST06): column order fixed by Focus LINKED_STUDENTS layout
select distinct
    -- grain projection: each row is one unordered sibling pair; every selected
    -- column is functionally determined by the (least, greatest) id pair
    least(p.id_a, p.id_b) as primary_student_id,
    greatest(p.id_a, p.id_b) as secondary_student_id,
    'sibling' as relationship,
from pairs as p

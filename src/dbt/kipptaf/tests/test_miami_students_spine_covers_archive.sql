-- Every student the frozen archive knows must survive into the spine, via the
-- Focus branch for those Focus carries and the archive branch for the 493 it
-- never received. A miss means the anti-join dropped a student from
-- dim_students; a duplicate means both branches kept the same one.
with
    archive as (
        select student_number,
        from {{ ref("stg_powerschool__students") }}
        where _dbt_source_project = 'kippmiami'
    ),

    spine as (
        select student_number, count(*) as spine_rows,
        from {{ ref("int_students__students") }}
        where _dbt_source_project = 'kippmiami'
        group by student_number
    )

select a.student_number, coalesce(s.spine_rows, 0) as spine_rows,
from archive as a
left join spine as s on a.student_number = s.student_number
where s.spine_rows is distinct from 1

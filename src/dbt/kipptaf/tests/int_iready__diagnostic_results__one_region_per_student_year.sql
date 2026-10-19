with
    checked as (
        select
            student_id,
            academic_year_int,
            `subject`,

            count(distinct _dbt_source_project) as n_regions,
        from {{ ref("int_iready__diagnostic_results") }}
        group by student_id, academic_year_int, `subject`
    )

select student_id, academic_year_int, `subject`, n_regions,
from checked
where n_regions > 1

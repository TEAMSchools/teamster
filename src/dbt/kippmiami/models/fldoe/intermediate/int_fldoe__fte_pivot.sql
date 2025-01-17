with
    fte as (
        select student_id, academic_year, survey_number, fte_capped,
        from {{ ref("stg_fldoe__fte") }}
    )

select student_id, academic_year, survey_1, survey_2, survey_3,
from
    fte pivot (
        max(fte_capped)
        for survey_number in (1 as `survey_1`, 2 as `survey_2`, 3 as `survey_3`)
    )

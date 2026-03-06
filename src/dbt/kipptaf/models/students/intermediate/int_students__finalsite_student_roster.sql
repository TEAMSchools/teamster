with
    -- next year new students
    current_students_ps_record as (
        select f.*,
        /* have to fix year so that it doesnt get dropped when PS gets rolled over and
           next year becomes current year */
        from {{ ref("int_finalsite__status_report_unpivot") }} as f
        where file_year = 2026
    )

select *,
from current_students_ps_record

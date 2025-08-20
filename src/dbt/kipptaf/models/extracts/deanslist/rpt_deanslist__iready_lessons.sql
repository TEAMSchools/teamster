select
    ir.student_number,
    ir.academic_year,
    ir.iready_subject,
    ir.week_start_monday as kipp_week_start,
    ir.week_end_sunday as kipp_week_end,
    ir.n_lessons_completed_week,
    ir.n_lessons_passed_week,
    ir.n_lessons_passed_y1,

    dt.term_id as dl_term_id,
from {{ ref("int_topline__iready_lessons_weeks") }} as ir
inner join
    {{ ref("stg_deanslist__terms") }} as dt
    on ir.deanslist_school_id = dt.school_id
    and ir.academic_year = dt.academic_year
    and ir.week_end_sunday between dt.start_date_date and dt.end_date_date
    and dt.term_type = 'Weeks'
    and dt.academic_year = {{ var("current_academic_year") }}

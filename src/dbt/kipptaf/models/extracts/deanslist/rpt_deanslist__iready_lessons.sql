select
    ir.student_id as student_number,
    ir.academic_year_int as academic_year,
    ir.subject as iready_subject,
    ir.date_range_start as kipp_week_start,
    ir.date_range_end as kipp_week_end,
    ir.all_lessons_completed as n_lessons_completed_week,
    ir.all_lessons_passed as n_lessons_passed_week,
    ir.total_lesson_time_on_task_min as total_lesson_time_on_task_min_week,
    ir.percent_all_lessons_passed as percent_all_lessons_passed_week,

    iy.all_lessons_completed as n_lessons_completed_y1,
    iy.all_lessons_passed as n_lessons_passed_y1,
    iy.total_lesson_time_on_task_min as total_lesson_time_on_task_min_y1,
    iy.percent_all_lessons_passed as percent_all_lessons_passed_y1,

    dt.term_id as dl_term_id,
from {{ ref("stg_iready__personalized_instruction_summary") }} as ir
inner join
    {{ ref("stg_iready__personalized_instruction_summary") }} as iy
    on ir.student_id = iy.student_id
    and ir.academic_year_int = iy.academic_year_int
    and ir.subject = iy.subject
    and iy.date_range = 'Year-to-Date'
inner join
    {{ ref("int_people__location_crosswalk") }} as cw on ir.school = cw.location_name
inner join
    {{ ref("stg_deanslist__terms") }} as dt
    on cw.location_deanslist_school_id = dt.school_id
    and ir.academic_year_int = dt.academic_year
    and ir.date_range_end between dt.start_date_date and dt.end_date_date
    and dt.term_type = 'Weeks'
where
    ir.date_range = 'Weekly'
    and ir.academic_year_int = {{ var("current_academic_year") }}

select
    co.academic_year,
    co.academic_year_display,
    co.student_number,
    co.student_name,
    co.grade_level,
    co.region,
    co.school_name,
    co.advisory as advisor_name,
    co.lep_status,
    co.iep_status,
    co.school_level,
    co.gender,
    co.ethnicity,
    co.schoolid,
    co.school,
    co.gifted_and_talented,
    co.lunch_status,
    co.iready_subject as `subject`,
    co.team,
    co.is_tutoring as tutoring_nj,
    co.state_test_proficiency,
    co.nj_student_tier,
    co.is_exempt_iready,
    co.is_sipps,
    co.is_magoosh,
    co.territory,
    co.hos as head_of_school,
    co.week_start_monday,
    co.week_end_sunday,

    il.lesson_id,
    il.lesson_name,
    il.lesson_objective,
    il.lesson_level,
    il.lesson_grade,
    il.passed_or_not_passed,
    il.total_time_on_lesson_min,
    il.completion_date,

    dr.test_round,
    dr.placement_3_level,
    dr.percent_progress_to_annual_typical_growth_percent
    as percent_progress_to_annual_typical_growth,
    dr.percent_progress_to_annual_stretch_growth_percent
    as percent_progress_to_annual_stretch_growth,
    dr.overall_relative_placement,
    dr.overall_relative_placement_int,
    dr.projected_sublevel,
    dr.projected_sublevel_number,
    dr.projected_sublevel_typical,
    dr.projected_sublevel_number_typical,
    dr.projected_sublevel_stretch,
    dr.projected_sublevel_number_stretch,
    dr.rush_flag,
    dr.mid_on_grade_level_scale_score,
    dr.overall_scale_score,

    iu.total_lesson_time_on_task_min as total_lesson_time_on_task_min_week,
    iu.all_lessons_completed as all_lessons_completed_week,
    iu.all_lessons_passed as all_lessons_passed_week,
    iu.percent_all_lessons_passed as percent_all_lessons_passed_week,

    cr.teacher_lastfirst as subject_teacher,
    cr.sections_section_number as subject_section,

    it.teacher_lastfirst as iready_teacher,

    if(
        current_date('{{ var("local_timezone") }}')
        between rt.start_date and rt.end_date,
        true,
        false
    ) as is_curterm,

    concat(
        left(co.student_first_name, 1), '. ', co.student_last_name
    ) as student_name_short,

    dr.mid_on_grade_level_scale_score
    - dr.overall_scale_score as scale_pts_to_mid_on_grade_level,

    row_number() over (
        partition by
            co.academic_year, co.student_number, co.iready_subject, co.week_start_monday
        order by il.completion_date desc
    ) as rn_subject_week,
from {{ ref("int_extracts__student_enrollments_subjects_weeks") }} as co
left join
    {{ ref("stg_google_sheets__reporting__terms") }} as rt
    on co.academic_year = rt.academic_year
    and co.region = rt.city
    and rt.type = 'IREX'
    and co.week_start_monday between rt.start_date and rt.end_date
left join
    {{ ref("stg_iready__personalized_instruction_summary") }} as iu
    on co.student_number = iu.student_id
    and co.iready_subject = iu.subject
    and co.week_start_monday = iu.date_range_start
    and co.academic_year = iu.academic_year_int
left join
    {{ ref("int_iready__instruction_by_lesson_union") }} as il
    on co.student_number = il.student_id
    and co.iready_subject = il.subject
    and il.completion_date between co.week_start_monday and co.week_end_sunday
    and il.academic_year_int = {{ var("current_academic_year") }}
left join
    {{ ref("base_iready__diagnostic_results") }} as dr
    on co.student_number = dr.student_id
    and co.academic_year = dr.academic_year_int
    and co.iready_subject = dr.subject
    and rt.name = dr.test_round
    and dr.rn_subj_round = 1
left join
    {{ ref("base_powerschool__course_enrollments") }} as cr
    on co.student_number = cr.students_student_number
    and co.yearid = cr.cc_yearid
    and co.schoolid = cr.cc_schoolid
    and co.powerschool_credittype = cr.courses_credittype
    and {{ union_dataset_join_clause(left_alias="co", right_alias="cr") }}
    and not cr.is_dropped_section
    and cr.rn_credittype_year = 1
left join
    {{ ref("base_powerschool__course_enrollments") }} as it
    on co.academic_year = it.cc_academic_year
    and co.student_number = it.students_student_number
    and it.courses_course_name like 'i-Ready%'
    and not it.is_dropped_section
    and not it.is_dropped_course
    and it.rn_course_number_year = 1
where
    co.rn_year = 1
    and co.enroll_status = 0
    and co.academic_year >= {{ var("current_academic_year") - 1 }}
    and co.grade_level <= 8

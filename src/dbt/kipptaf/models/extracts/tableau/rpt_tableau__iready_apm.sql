with
    date_range as (
        select safe_cast(date_day as date) as date_day,
        from {{ ref("utils__date_spine") }}
        where
            date_day
            between date({{ var("current_academic_year") }}, 7, 1) and current_date(
                '{{ var("local_timezone") }}'
            )
    ),

    expanded_terms as (
        select
            academic_year,
            name,
            start_date,
            case
                region
                when 'KIPP Miami'
                then 'Miami'
                when 'TEAM Academy Charter School'
                then 'Newark'
                when 'KIPP Cooper Norcross Academy'
                then 'Camden'
            end as region,
            -- end_date contains test window end date
            -- this needs continuous dates
            coalesce(
                lead(start_date, 1) over (
                    partition by academic_year, region order by code asc
                )
                - 1,
                date({{ var("current_academic_year") }} + 1, 06, 30)
            ) as end_date,
        from {{ ref("stg_reporting__terms") }}
        where type = 'IR'
    )

select
    co.student_number,
    co.lastfirst,
    co.grade_level,
    co.region,
    co.school_name,
    co.advisor_lastfirst as advisor_name,
    co.lep_status,
    co.spedlep as iep_status,
    co.school_level,
    co.gender,
    co.ethnicity,
    co.schoolid,
    co.school_abbreviation,

    subj as subject,

    w.date_day as `date`,

    hr.sections_section_number as team,

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

    iu.last_week_start_date,
    iu.last_week_end_date,
    iu.last_week_time_on_task_min,

    f.tutoring_nj as is_tutoring,
    f.state_test_proficiency,
    f.nj_student_tier,
    f.is_exempt_iready,
    f.territory,

    lc.head_of_school_preferred_name_lastfirst as head_of_school,

    cr.teacher_lastfirst as subject_teacher,
    cr.sections_section_number as subject_section,

    if(
        current_date('{{ var("local_timezone") }}')
        between rt.start_date and rt.end_date,
        true,
        false
    ) as is_curterm,
    concat(left(co.first_name, 1), '. ', co.last_name) as student_name_short,
    dr.mid_on_grade_level_scale_score
    - dr.overall_scale_score as scale_pts_to_mid_on_grade_level,
from {{ ref("base_powerschool__student_enrollments") }} as co
cross join unnest(['Reading', 'Math']) as subj
cross join date_range as w
left join
    expanded_terms as rt
    on co.academic_year = rt.academic_year
    and co.region = rt.region
    and w.date_day between rt.start_date and rt.end_date
left join
    {{ ref("stg_iready__personalized_instruction_by_lesson") }} as il
    on co.student_number = il.student_id
    and co.academic_year = il.academic_year_int
    and subj = il.subject
    and w.date_day = il.completion_date
left join
    {{ ref("base_iready__diagnostic_results") }} as dr
    on co.student_number = dr.student_id
    and co.academic_year = dr.academic_year_int
    and subj = dr.subject
    and rt.name = dr.test_round
    and dr.rn_subj_round = 1
left join
    {{ ref("snapshot_iready__instructional_usage_data") }} as iu
    on co.student_number = iu.student_id
    and co.academic_year = cast(left(iu.academic_year, 4) as int)
    and subj = iu.subject
    and w.date_day = iu.last_week_start_date
left join
    {{ ref("base_powerschool__course_enrollments") }} as hr
    on co.student_number = hr.students_student_number
    and co.yearid = hr.cc_yearid
    and co.schoolid = hr.cc_schoolid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="hr") }}
    and not hr.is_dropped_section
    and hr.cc_course_number = 'HR'
    and hr.rn_course_number_year = 1
left join
    {{ ref("int_reporting__student_filters") }} as f
    on co.student_number = f.student_number
    and co.academic_year = f.academic_year
    and subj = f.iready_subject
left join
    {{ ref("int_people__leadership_crosswalk") }} as lc
    on co.schoolid = lc.home_work_location_powerschool_school_id
left join
    {{ ref("base_powerschool__course_enrollments") }} as cr
    on co.student_number = cr.students_student_number
    and co.yearid = cr.cc_yearid
    and co.schoolid = cr.cc_schoolid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="cr") }}
    and not cr.is_dropped_section
    and cr.courses_credittype in ('ENG', 'MATH')
    and case when subj = 'Reading' then 'ENG' when subj = 'Math' then 'MATH' end
    = cr.courses_credittype
    and cr.rn_credittype_year = 1
where
    co.academic_year = {{ var("current_academic_year") }}
    and co.rn_year = 1
    and co.enroll_status = 0
    and co.grade_level <= 8

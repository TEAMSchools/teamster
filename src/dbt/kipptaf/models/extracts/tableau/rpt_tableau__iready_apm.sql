with
    expanded_terms as (
        select
            academic_year,
            `name`,
            `start_date`,

            case
                region
                when 'KIPP Miami'
                then 'Miami'
                when 'TEAM Academy Charter School'
                then 'Newark'
                when 'KIPP Cooper Norcross Academy'
                then 'Camden'
            end as region,

            /* end_date contains test window end date this needs continuous dates */
            coalesce(
                lead(`start_date`, 1) over (
                    partition by academic_year, region order by code asc
                )
                - 1,
                '{{ var("current_fiscal_year") }}-06-30'
            ) as end_date,
        from {{ ref("stg_reporting__terms") }}
        where type = 'IR'
    ),

    iready_teacher as (
        select
            cc_academic_year,
            students_student_number,
            courses_course_name,
            teacher_lastfirst,

        from {{ ref("base_powerschool__course_enrollments") }}
        where
            courses_course_name like 'i-Ready%'
            and not is_dropped_section
            and not is_dropped_course
            and rn_course_number_year = 1
    )

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

    subj as `subject`,

    w.week_start_monday,
    w.week_end_sunday,

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

    f.is_tutoring as tutoring_nj,
    f.state_test_proficiency,
    f.nj_student_tier,
    f.is_exempt_iready,
    f.territory,

    lc.head_of_school_preferred_name_lastfirst as head_of_school,

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
from {{ ref("int_extracts__student_enrollments") }} as co
inner join
    {{ ref("int_powerschool__calendar_week") }} as w
    on co.schoolid = w.schoolid
    and co.academic_year = w.academic_year
    and w.week_start_monday between co.entrydate and co.exitdate
    and {{ union_dataset_join_clause(left_alias="co", right_alias="w") }}
cross join unnest(['Reading', 'Math']) as subj
left join
    expanded_terms as rt
    on co.academic_year = rt.academic_year
    and co.region = rt.region
    and w.week_start_monday between rt.start_date and rt.end_date
left join
    {{ ref("int_iready__instruction_by_lesson_union") }} as il
    on co.student_number = il.student_id
    and subj = il.subject
    and il.completion_date between w.week_start_monday and w.week_end_sunday
    and il.academic_year_int = {{ var("current_academic_year") }}
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
    and subj = iu.subject
    and w.week_start_monday = iu.last_week_start_date
    and iu.academic_year_int = {{ var("current_academic_year") }}
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
    {{ ref("int_extracts__student_enrollments_subjects") }} as f
    on co.student_number = f.student_number
    and co.academic_year = f.academic_year
    and subj = f.iready_subject
    and f.rn_year = 1
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
left join
    iready_teacher as it
    on co.academic_year = it.cc_academic_year
    and co.student_number = it.students_student_number
where
    co.academic_year >= {{ var("current_academic_year") - 1 }}
    and co.enroll_status = 0
    and co.grade_level <= 8
    and co.rn_year = 1

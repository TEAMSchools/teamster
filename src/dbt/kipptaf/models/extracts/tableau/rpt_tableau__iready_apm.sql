with
    date_range as (
        select
            {{
                teamster_utils.date_to_fiscal_year(
                    date_field="date_day", start_month=7, year_source="start"
                )
            }} as academic_year, cast(date_day as date) as date,
        from {{ ref("utils__date_spine") }}
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

    w.date,

    hr.sections_section_number as team,

    il.lesson_id,
    il.passed_or_not_passed,
    il.total_time_on_lesson_min,
    il.completion_date,

    dr.test_round,
    dr.placement_3_level,
    dr.percent_progress_to_annual_typical_growth_percent
    as percent_progress_to_annual_typical_growth,
    dr.percent_progress_to_annual_stretch_growth_percent
    as percent_progress_to_annual_stretch_growth,
    -- TODO: these don't exist
    null as last_week_start_date,
    null as last_week_end_date,

    iu.last_week_time_on_task_min,

    if(sp.specprog_name is not null, true, false) as is_tutoring,
from {{ ref("base_powerschool__student_enrollments") }} as co
cross join unnest(['Reading', 'Math']) as subj
inner join
    date_range as w
    on co.academic_year = w.academic_year
    and w.date <= current_date('America/New_York') + 1
left join
    expanded_terms as rt
    on rt.academic_year = co.academic_year
    and w.date between rt.start_date and rt.end_date
    and co.region = rt.region
left join
    {{ ref("stg_iready__personalized_instruction_by_lesson") }} as il
    on il.student_id = co.student_number
    and il.academic_year_int = co.academic_year
    and subj = il.subject
    and il.completion_date = w.date
left join
    {{ ref("base_iready__diagnostic_results") }} as dr
    on co.student_number = dr.student_id
    and co.academic_year = dr.academic_year_int
    and subj = dr.subject
    and dr.test_round = rt.name
    and dr.rn_subj_round = 1
left join
    {{ ref("stg_iready__instructional_usage_data") }} as iu
    on co.student_number = iu.student_id
    and co.academic_year = cast(left(iu.academic_year, 4) as int64)
    and subj = iu.subject
    and w.date = parse_date("%m/%d/%Y", iu.last_week_start_date)
left join
    {{ ref("base_powerschool__course_enrollments") }} as hr
    on co.student_number = hr.students_student_number
    and co.yearid = hr.cc_yearid
    and co.schoolid = hr.cc_schoolid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="hr") }}
    and hr.cc_course_number = 'HR'
    and not hr.is_dropped_section
    and hr.rn_course_number_year = 1
left join
    {{ ref("int_powerschool__spenrollments") }} as sp
    on co.studentid = sp.studentid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="sp") }}
    and co.academic_year = sp.academic_year
    and current_date('America/New_York') between sp.enter_date and sp.exit_date
    and sp.specprog_name = 'Tutoring'
where
    co.academic_year = {{ var("current_academic_year") }}
    and co.rn_year = 1
    and co.enroll_status = 0
    and co.grade_level < 9

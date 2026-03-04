with
    iready_lessons as (
        select
            student_id,
            `subject`,

            count(distinct lesson_id) as total_lessons,
            sum(passed_or_not_passed_numeric) as lessons_passed,
        from {{ ref("int_iready__instruction_by_lesson") }}
        where
            completion_date in unnest(
                generate_date_array(
                    date_sub(
                        date_trunc(current_date('{{ var("local_timezone") }}'), week),
                        interval 1 week
                    ),
                    last_day(current_date('{{ var("local_timezone") }}'), week)
                )
            )
        group by student_id, `subject`
    ),

    pre_filter_qaf as (
        select powerschool_student_number, subject_area, module_code, percent_correct,
        from {{ ref("int_assessments__response_rollup") }}
        where
            module_type = 'QAF'
            and response_type = 'overall'
            {# TODO: document or use var #}
            and academic_year = 2023
    ),

    qaf_pct_correct as (
        select powerschool_student_number, subject_area, qaf1, qaf2, qaf3, qaf4,
        from
            pre_filter_qaf pivot (
                max(percent_correct) for module_code in ('QAF1', 'QAF2', 'QAF3', 'QAF4')
            )
    ),

    scale_crosswalk as (
        select
            administration_window,
            academic_year,

            'FAST_NEW' as source_system,
            'FL' as destination_system,
        from
            unnest(
                generate_array(2023, {{ var("current_academic_year") }})
            ) as academic_year
        cross join unnest(['PM1', 'PM2', 'PM3']) as administration_window

        union all

        select
            administration_window,

            2022 as academic_year,
            'FAST' as source_system,
            'FL' as destination_system,
        from unnest(['PM1', 'PM2']) as administration_window

        union all

        select
            'PM3' as administration_window,
            2022 as academic_year,
            'FAST_NEW' as source_system,
            'FL' as destination_system,
    )

select
    co.academic_year,
    co.student_number,
    co.state_studentnumber as mdcps_id,
    co.fleid,
    co.student_name as lastfirst,
    co.grade_level,
    co.schoolid,
    co.school_name,
    co.advisory_name as team,
    co.school as school_abbreviation,
    co.year_in_network,
    co.gender,
    co.ethnicity,
    co.spedlep as iep_status,
    co.lep_status,
    co.lunch_status as lunchstatus,
    co.is_retained_year,
    co.enroll_status,
    co.is_fldoe_fte_2 as is_enrolled_fte2,
    co.is_fldoe_fte_3 as is_enrolled_fte3,
    co.is_fldoe_fte_all as is_enrolled_fte,
    co.fast_subject as fsa_subject,
    co.iready_subject,
    co.territory,
    co.nj_student_tier as student_tier,

    administration_window,

    ce.cc_course_number as course_number,
    ce.courses_course_name as course_name,
    ce.sections_section_number as section_number,
    ce.teacher_lastfirst as teacher_name,
    ce.teachernumber,

    ir.total_lessons,
    ir.lessons_passed,

    ia.qaf1,
    ia.qaf2,
    ia.qaf3,
    ia.qaf4,

    dr.overall_scale_score as diagnostic_scale,
    dr.overall_relative_placement as diagnostic_overall_relative_placement,
    dr.annual_typical_growth_measure,
    dr.annual_stretch_growth_measure,
    dr.most_recent_overall_scale_score as recent_scale,
    dr.most_recent_overall_relative_placement as recent_overall_relative_placement,
    dr.most_recent_overall_placement as recent_overall_placement,
    dr.most_recent_diagnostic_gain as diagnostic_gain,
    dr.most_recent_lexile_measure as lexile_recent,
    dr.most_recent_lexile_range as lexile_range_recent,
    dr.most_recent_rush_flag as rush_flag,
    dr.projected_sublevel_recent as projected_sublevel,
    dr.projected_sublevel_number_recent as projected_sublevel_number,
    dr.proficent_scale_score as scale_for_proficiency,
    dr.progress_to_typical,
    dr.progress_to_stretch,
    dr.scale_points_to_proficiency,

    ft.achievement_level,
    ft.scale_score,
    ft.scale_score_prev,
    ft.sublevel_name as fast_sublevel_name,
    ft.sublevel_number as fast_sublevel_number,
    ft.scale_for_growth as fast_scale_for_growth,
    ft.scale_for_proficiency as fast_scale_for_proficiency,
    ft.points_to_growth as fast_scale_points_to_growth,
    ft.points_to_proficiency as fast_scale_points_to_proficiency,
    ft.achievement_level_int as fast_level_int,

    p.prev_pm3_scale,
    p.prev_pm3_level_int,
    p.prev_pm3_sublevel_name,
    p.prev_pm3_sublevel_number,
    p.fldoe_percentile_rank,
    p.scale_for_growth as scale_for_growth_prev_pm3,
    p.sublevel_for_growth as sublevel_for_growth_prev_pm3,
    p.sublevel_number_for_growth as sublevel_number_for_growth_prev_pm3,
    p.scale_for_proficiency as scale_for_proficiency_prev_pm3,
    p.scale_points_to_growth_pm3,
    p.scale_points_to_proficiency_pm3,

    fs.standard as standard_domain,
    fs.performance as mastery_indicator,
    fs.performance as mastery_number,

    null as is_present_fte2,
    null as is_present_fte3,

    round(ir.lessons_passed / ir.total_lessons, 2) as pct_passed,

    if(p.fldoe_percentile_rank < .255, true, false) as is_low_25,

    if(
        not co.is_retained_year
        and co.grade_level = 3
        and co.fast_subject = 'English Language Arts'
        and ft.achievement_level_int = 1,
        1,
        0
    ) as gr3_retention_flag,

    case ft.is_proficient when true then 1.0 when false then 0.0 end as is_proficient,

    case
        when
            p.prev_pm3_scale is not null
            and ft.sublevel_number > p.prev_pm3_sublevel_number
        then true
        when p.prev_pm3_scale is not null and ft.sublevel_number = 8
        then true
        when
            p.prev_pm3_scale is not null
            and p.prev_pm3_sublevel_number in (6, 7)
            and p.prev_pm3_sublevel_number = ft.sublevel_number
            and ft.scale_score > p.prev_pm3_scale
        then true
        when p.prev_pm3_scale is not null
        then false
    end as is_fldoe_growth,

    row_number() over (
        partition by
            co.student_number, co.academic_year, co.fast_subject, administration_window
        order by fs.standard asc
    ) as rn_test_fast,

    row_number() over (
        partition by co.student_number, co.academic_year, co.fast_subject
        order by administration_window desc
    ) as rn_year_fast,
from {{ ref("int_extracts__student_enrollments_subjects") }} as co
cross join unnest(['PM1', 'PM2', 'PM3']) as administration_window
left join
    {{ ref("base_powerschool__course_enrollments") }} as ce
    on co.student_number = ce.students_student_number
    and co.academic_year = ce.cc_academic_year
    and co.powerschool_credittype = ce.courses_credittype
    and ce.rn_credittype_year = 1
    and not ce.is_dropped_section
left join
    iready_lessons as ir
    on co.student_number = ir.student_id
    and co.iready_subject = ir.subject
left join
    qaf_pct_correct as ia
    on co.student_number = ia.powerschool_student_number
    and co.illuminate_subject_area = ia.subject_area
left join
    {{ ref("int_iready__diagnostic_results") }} as dr
    on co.student_number = dr.student_id
    and co.academic_year = dr.academic_year_int
    and co.iready_subject = dr.subject
    and dr.baseline_diagnostic_y_n = 'Y'
left join
    {{ ref("int_fldoe__all_assessments") }} as ft
    on co.fleid = ft.student_id
    and co.academic_year = ft.academic_year
    and co.fast_subject = ft.assessment_subject
    and administration_window = ft.administration_window
    and ft.assessment_name = 'FAST'
left join
    {{ ref("int_assessments__fast_previous_year") }} as p
    on co.student_number = p.student_number
    and co.academic_year = p.academic_year
    and co.fast_subject = p.assessment_subject
left join
    {{ ref("int_fldoe__fast_standard_performance_unpivot") }} as fs
    on co.fleid = fs.student_id
    and co.academic_year = fs.academic_year
    and co.fast_subject = fs.assessment_subject
    and administration_window = fs.administration_window
where
    co.region = 'Miami'
    and co.is_enrolled_y1
    and co.rn_year = 1
    and co.academic_year >= {{ var("current_academic_year") - 1 }}
    and co.grade_level >= 3

with
    subjects as (
        select
            'Reading' as iready_subject,
            'ELAReading' as fast_subject,
            'ENG' as ps_credittype,
            'Text Study' as illuminate_subject,

        union all

        select
            'Math' as iready_subject,
            'Mathematics' as fast_subject,
            'MATH' as ps_credittype,
            'Mathematics' as illuminate_subject
    ),

    iready_lessons as (
        select
            student_id,
            subject,
            count(distinct lesson_id) as total_lessons,
            sum(passed_or_not_passed_numeric) as lessons_passed,
        from {{ ref("stg_iready__personalized_instruction_by_lesson") }}
        where
            completion_date in (
                select date_value
                from
                    unnest(
                        generate_date_array(
                            date_sub(
                                date_trunc(current_date('America/New_York'), week),
                                interval 1 week
                            ),
                            last_day(current_date('America/New_York'), week)
                        )
                    ) as date_value
            )
        group by student_id, subject
    ),

    qaf_pct_correct as (
        -- TODO: should this be filtered by subject?
        select powerschool_student_number, subject_area, qaf1, qaf2, qaf3, qaf4,
        from
            {{ ref("int_assessments__response_rollup") }} pivot (
                max(percent_correct) for module_number
                in ('QAF1', 'QAF2', 'QAF3', 'QAF4')
            )
        where module_type = 'QAF' and academic_year = {{ var("current_academic_year") }}
    )

select
    co.academic_year,
    co.student_number,
    co.state_studentnumber as mdcps_id,
    co.fleid,
    co.lastfirst,
    co.grade_level,
    co.schoolid,
    co.school_name,
    co.advisory_name as team,
    co.school_abbreviation,
    co.year_in_network,
    co.gender,
    co.ethnicity,
    co.spedlep as iep_status,
    co.lep_status,
    co.lunch_status as lunchstatus,
    co.is_retained_year,

    subj.fast_subject as fsa_subject,
    subj.iready_subject,

    administration_window,

    ce.cc_course_number as course_number,
    ce.courses_course_name as course_name,
    ce.sections_section_number as section_number,
    ce.teacher_lastfirst as teacher_name,

    ir.total_lessons,
    ir.lessons_passed,
    round(ir.lessons_passed / ir.total_lessons, 2) as pct_passed,

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

    ft.administration_window as pm_round,
    ft.achievement_level,
    ft.scale_score,
    ft.scale_score_prev,

    cwf.sublevel_name as fast_sublevel_name,
    cwf.sublevel_number as fast_sublevel_number,

    fs.standard as standard_domain,
    fs.performance as mastery_indicator,
    fs.performance as mastery_number,

    if(
        not co.is_retained_year
        and co.grade_level = 3
        and subj.fast_subject = 'ELA'
        and ft.achievement_level_int < 2,
        1,
        0
    ) as gr3_retention_flag,

    row_number() over (
        partition by
            co.fleid, co.academic_year, subj.fast_subject, ft.administration_window
        order by fs.standard asc
    ) as rn_test_fast,
from {{ ref("base_powerschool__student_enrollments") }} as co
cross join subjects as subj
cross join unnest(["PM1", "PM2", "PM3"]) as administration_window
left join
    {{ ref("base_powerschool__course_enrollments") }} as ce
    on co.student_number = ce.students_student_number
    and co.academic_year = ce.cc_academic_year
    and subj.ps_credittype = ce.courses_credittype
    and ce.rn_credittype_year = 1
    and not ce.is_dropped_section
left join
    iready_lessons as ir
    on co.student_number = ir.student_id
    and subj.iready_subject = ir.subject
left join
    qaf_pct_correct as ia
    on co.student_number = ia.powerschool_student_number
    and subj.illuminate_subject = ia.subject_area
left join
    {{ ref("base_iready__diagnostic_results") }} as dr
    on co.student_number = dr.student_id
    and co.academic_year = dr.academic_year_int
    and subj.iready_subject = dr.subject
    and dr.baseline_diagnostic_y_n = 'Y'
left join
    {{ ref("stg_fldoe__fast") }} as ft
    on co.fleid = ft.student_id
    and co.academic_year = ft.academic_year
    and subj.fast_subject = ft.assessment_subject
    and administration_window = ft.administration_window
left join
    {{ ref("stg_assessments__iready_crosswalk") }} as cwf
    on ft.assessment_subject = cwf.test_name
    and ft.scale_score between cwf.scale_low and cwf.scale_high
    and cwf.source_system = 'FSA'
left join
    {{ ref("int_fldoe__fast_standard_performance_unpivot") }} as fs
    on co.fleid = fs.student_id
    and co.academic_year = fs.academic_year
    and subj.fast_subject = fs.assessment_subject
    and administration_window = fs.administration_window
where
    co.region = 'Miami'
    and co.is_enrolled_y1
    and co.rn_year = 1
    and co.academic_year >= {{ var("current_academic_year") }} - 1
    and co.grade_level >= 3

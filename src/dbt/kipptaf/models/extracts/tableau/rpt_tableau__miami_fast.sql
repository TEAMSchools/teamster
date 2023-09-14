with
    subjects as (
        select
            s.`value` as iready_subject,
            if(s.`value` = 'Reading', 'ELA', s.`value`) as fsa_subject,
            case
                s.`value` when 'Reading' then 'ENG' when 'Math' then 'MATH'
            end as credittype,
        from string_split('Reading,Math', ',') as s
    ),

    current_week as (
        select tw.`date`
        from utilities.reporting_days as td
        inner join
            utilities.reporting_days as tw
            on td.year_part = tw.year_part
            and ((td.week_part = tw.week_part) or (td.week_part - 1 = tw.week_part))
        where td.`date` = current_date('{{ var("local_timezone") }}')
    ),

    iready_lessons as (
        select
            student_id,
            subject,
            count(distinct lesson_id) as total_lessons,
            sum(if(passed_or_not_passed = 'Passed', 1.0, 0.0)) as lessons_passed,
        from iready.personalized_instruction_by_lesson
        where completion_date in (select `date` from current_week)
        group by student_id, subject
    ),

    qaf_pct_correct as (
        select local_student_id, qaf1, qaf2, qaf3, qaf4,
        from
            ... pivot (
                max(percent_correct) for module_number
                in ('QAF1', 'QAF2', 'QAF3', 'QAF4')
            )
        where module_type = 'QAF'
    )

select
    co.student_number,
    co.state_studentnumber as mdcps_id,
    co.fleid,
    co.lastfirst,
    co.grade_level,
    co.schoolid,
    co.school_name,
    co.team,
    co.school_abbreviation,
    co.year_in_network,
    co.gender,
    co.ethnicity,
    co.iep_status,
    co.lep_status,
    co.lunchstatus,
    co.is_retained_year,

    subj.fsa_subject,
    subj.iready_subject,

    ce.course_number,
    ce.course_name,
    ce.section_number,
    ce.teacher_name,

    ir.total_lessons,
    ir.lessons_passed,
    round(ir.lessons_passed / ir.total_lessons, 2) as pct_passed

    ia.qaf1,
    ia.qaf2,
    ia.qaf3,
    ia.qaf4,

    dr1.overall_scale_score as diagnostic_scale,
    dr1.overall_relative_placement as diagnostic_overall_relative_placement,
    dr1.annual_typical_growth_measure,
    dr1.annual_stretch_growth_measure,

    dr2.overall_scale_score as recent_scale,
    dr2.overall_relative_placement as recent_overall_relative_placement,
    dr2.overall_placement as recent_overall_placement,
    dr2.diagnostic_gain,
    dr2.lexile_measure as lexile_recent,
    dr2.lexile_range as lexile_range_recent,
    dr2.rush_flag,

    cw1.sublevel_name as projected_sublevel,
    cw1.sublevel_number as projected_sublevel_number,

    cw2.scale_low as scale_for_proficiency,

    ft.pm_round,
    ft.achievement_level,
    ft.scale_score,
    ft.scale_score_prev,
    ft.standard_domain,
    ft.mastery_indicator,
    ft.mastery_number,
    ft.rn_test as rn_test_fast,

    cw3.sublevel_name as fast_sublevel_name,
    cw3.sublevel_number as fast_sublevel_number,

    round(
        dr2.diagnostic_gain / dr1.annual_typical_growth_measure, 2
    ) as progress_to_typical,
    round(
        dr2.diagnostic_gain / dr1.annual_stretch_growth_measure, 2
    ) as progress_to_stretch,

    case
        when cw2.scale_low - dr2.overall_scale_score <= 0
        then 0
        else cw2.scale_low - dr2.overall_scale_score
    end as scale_points_to_proficiency,

    if(
        not co.is_retained_year
        and co.grade_level = 3
        and subj.fsa_subject = 'ELA'
        and ft.achievement_level < 2,
        1,
        0
    ) as gr3_retention_flag,
from {{ ref('base_powerschool__student_enrollments') }} as co
cross join subjects as subj
left join
    kippmiami.powerschool.course_enrollments_current_static as ce
    on co.student_number = ce.student_number
    and subj.credittype = ce.credittype
    and ce.rn_subject = 1
    and not ce.is_dropped_section
left join
    iready_lessons as ir
    on co.student_number = ir.student_id
    and subj.iready_subject = ir.subject
left join qaf_pct_correct as ia on co.student_number = ia.local_student_id
left join
    gabby.iready.diagnostic_results as dr1
    on co.student_number = dr1.student_id
    and co.academic_year = dr1.academic_year
    and subj.iready_subject = dr1._file
    and dr1.baseline_diagnostic_y_n_ = 'Y'
left join
    gabby.iready.diagnostic_results as dr2
    on dr1.student_id = dr2.student_id
    and dr1._file = dr2._file
    and dr2.most_recent_diagnostic_y_n_ = 'Y'
left join
    assessments.fsa_iready_crosswalk as cw1
    on co.grade_level = cw1.grade_level
    and dr1._file = cw1.test_name
    and dr2.overall_scale_score between cw1.scale_low and cw1.scale_high
    and cw1.source_system = 'i-Ready'
    and cw1.destination_system = 'FL'
left join
    assessments.fsa_iready_crosswalk as cw2
    on co.grade_level = cw2.grade_level
    and dr1._file = cw2.test_name
    and cw2.source_system = 'i-Ready'
    and cw2.destination_system = 'FL'
    and cw2.sublevel_name = 'Level 3'
left join
    kippmiami.fast.student_data_long as ft
    on co.fleid = ft.fleid
    and subj.iready_subject = ft.fast_subject
left join
    assessments.fsa_iready_crosswalk as cw3
    on ft.fast_test = cw3.test_name
    and ft.scale_score between cw3.scale_low and cw3.scale_high
    and cw3.source_system = 'FSA'
where
    co.academic_year = {{ var("current_academic_year") }}
    and co.rn_year = 1
    and co.enroll_status = 0
    and co.grade_level >= 3

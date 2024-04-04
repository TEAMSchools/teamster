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
            'Mathematics' as illuminate_subject,
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
                select date_value,
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
        select powerschool_student_number, subject_area, qaf1, qaf2, qaf3, qaf4,
        from
            {{ ref("int_assessments__response_rollup") }} pivot (
                max(percent_correct) for module_number
                in ('QAF1', 'QAF2', 'QAF3', 'QAF4')
            )
        where
            module_type = 'QAF'
            and academic_year = {{ var("current_academic_year") }}
            and response_type = 'overall'
    ),

    scale_crosswalk as (
        select
            2022 as academic_year,
            administration_window,
            'FAST' as source_system,
            'FL' as destination_system,
        from unnest(['PM1', 'PM2']) as administration_window
        union all
        select
            2022 as academic_year,
            'PM3' as administration_window,
            'FAST_NEW' as source_system,
            'FL' as destination_system,
        union all
        select
            academic_year,
            administration_window,
            'FAST_NEW' as source_system,
            'FL' as destination_system,
        from
            unnest(
                generate_array(2023, {{ var("current_academic_year") }})
            ) as academic_year
        cross join unnest(['PM1', 'PM2', 'PM3']) as administration_window
    ),

    prev_pm3 as (
        select
            f.student_id,
            f.assessment_subject,
            f.scale_score as prev_pm3_scale,
            f.achievement_level_int as prev_pm3_level_int,

            i.sublevel_name as prev_pm3_sublevel_name,
            i.sublevel_number as prev_pm3_sublevel_number,

            f.academic_year + 1 as academic_year_next,
            round(
                rank() over (
                    partition by
                        f.academic_year, f.assessment_grade, f.assessment_subject
                    order by f.scale_score asc
                ) / count(*) over (
                    partition by
                        f.academic_year, f.assessment_grade, f.assessment_subject
                ),
                4
            ) as fldoe_percentile_rank,
        from {{ ref("stg_fldoe__fast") }} as f
        left join
            {{ ref("stg_assessments__iready_crosswalk") }} as i
            on f.assessment_subject = i.test_name
            and f.assessment_grade = i.grade_level
            and f.scale_score between i.scale_low and i.scale_high
            and i.source_system = 'FAST_NEW'
            and i.destination_system = 'FL'
        where f.administration_window = 'PM3'
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
    co.enroll_status,

    fte.is_enrolled_fte2,
    fte.is_enrolled_fte3,
    fte.is_present_fte2,
    fte.is_present_fte3,

    subj.fast_subject as fsa_subject,
    subj.iready_subject,

    administration_window,

    ce.cc_course_number as course_number,
    ce.courses_course_name as course_name,
    ce.sections_section_number as section_number,
    ce.teacher_lastfirst as teacher_name,

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

    p.prev_pm3_scale,
    p.prev_pm3_level_int,
    p.prev_pm3_sublevel_name,
    p.prev_pm3_sublevel_number,
    p.fldoe_percentile_rank,

    cwf.sublevel_name as fast_sublevel_name,
    cwf.sublevel_number as fast_sublevel_number,

    fs.standard as standard_domain,
    fs.performance as mastery_indicator,
    fs.performance as mastery_number,

    sf.territory,

    if(fte.is_enrolled_fte2 and fte.is_enrolled_fte3, true, false) as is_enrolled_fte,

    round(ir.lessons_passed / ir.total_lessons, 2) as pct_passed,

    case ft.is_proficient when true then 1.0 when false then 0.0 end as is_proficient,

    if(
        not co.is_retained_year
        and co.grade_level = 3
        and subj.fast_subject = 'ELAReading'
        and not ft.is_proficient,
        1,
        0
    ) as gr3_retention_flag,

    if(p.fldoe_percentile_rank < .255, true, false) as is_low_25,

    case
        when
            p.prev_pm3_scale is not null
            and cwf.sublevel_number > p.prev_pm3_sublevel_number
        then true
        when p.prev_pm3_scale is not null and cwf.sublevel_number = 8
        then true
        when
            p.prev_pm3_scale is not null
            and p.prev_pm3_sublevel_number in (6, 7)
            and p.prev_pm3_sublevel_number = cwf.sublevel_number
            and ft.scale_score > p.prev_pm3_scale
        then true
        when p.prev_pm3_scale is not null
        then false
    end as is_fldoe_growth,

    row_number() over (
        partition by
            co.student_number,
            co.academic_year,
            subj.fast_subject,
            administration_window
        order by fs.standard asc
    ) as rn_test_fast,
from {{ ref("base_powerschool__student_enrollments") }} as co
cross join subjects as subj
cross join unnest(['PM1', 'PM2', 'PM3']) as administration_window
left join
    {{ ref("int_students__fldoe_fte") }} as fte
    on co.studentid = fte.studentid
    and co.yearid = fte.yearid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="fte") }}
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
    prev_pm3 as p
    on co.fleid = p.student_id
    and co.academic_year = p.academic_year_next
    and subj.fast_subject = p.assessment_subject
left join
    scale_crosswalk as sc
    on ft.academic_year = sc.academic_year
    and ft.administration_window = sc.administration_window
left join
    {{ ref("stg_assessments__iready_crosswalk") }} as cwf
    on ft.assessment_subject = cwf.test_name
    and ft.assessment_grade = cwf.grade_level
    and ft.scale_score between cwf.scale_low and cwf.scale_high
    and sc.source_system = cwf.source_system
    and sc.destination_system = cwf.destination_system
left join
    {{ ref("int_fldoe__fast_standard_performance_unpivot") }} as fs
    on co.fleid = fs.student_id
    and co.academic_year = fs.academic_year
    and subj.fast_subject = fs.assessment_subject
    and administration_window = fs.administration_window
left join
    {{ ref("int_reporting__student_filters") }} as sf
    on co.student_number = sf.student_number
    and co.academic_year = sf.academic_year
    and subj.iready_subject = sf.iready_subject
where
    co.region = 'Miami'
    and co.is_enrolled_y1
    and co.rn_year = 1
    and co.academic_year >= {{ var("current_academic_year") }} - 1
    and co.grade_level >= 3

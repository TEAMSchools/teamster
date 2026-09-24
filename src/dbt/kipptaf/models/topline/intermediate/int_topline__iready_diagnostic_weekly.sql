with
    baseline_diagnostic as (
        select
            student_id,
            academic_year_int,
            `subject`,
            overall_relative_placement_int,
            completion_date,
        from {{ ref("int_iready__diagnostic_results") }}
        where baseline_diagnostic_y_n = 'Y'
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="baseline_diagnostic",
                partition_by="student_id, academic_year_int, subject",
                order_by="completion_date desc",
            )
        }}
    ),

    subject_weeks as (
        select
            student_number,
            academic_year,
            week_start_monday,
            week_end_sunday,
            discipline,
            iready_subject,
            region,
            entrydate,
            is_enrolled_week,
            _dbt_source_project,
        from {{ ref("int_extracts__student_enrollments_subjects_weeks") }}
        where academic_year >= {{ var("current_academic_year") - 1 }}
    ),

    subject_weeks_deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="subject_weeks",
                partition_by="student_number, academic_year, week_start_monday, discipline",
                order_by="is_enrolled_week desc, entrydate desc",
            )
        }}
    )

select
    cw.student_number,
    cw.academic_year,
    cw.week_start_monday,
    cw.week_end_sunday,
    cw.discipline,

    case
        when ir.is_proficient then 1 when not ir.is_proficient then 0
    end as is_proficient,

    case
        when
            d.overall_relative_placement_int < 3
            and ir.percent_progress_to_annual_stretch_growth_percent >= 1
        then 1
        when
            d.overall_relative_placement_int < 3
            and ir.percent_progress_to_annual_stretch_growth_percent < 1
        then 0
    end as is_bfb_stretch_growth_int,
from subject_weeks_deduplicate as cw
inner join
    {{ ref("stg_google_sheets__reporting__terms") }} as rt
    on cw.academic_year = rt.academic_year
    and cw.region = rt.city
    and cw.week_start_monday between rt.start_date and rt.end_date
    and rt.type = 'IREX'
left join
    {{ ref("int_iready__diagnostic_results") }} as ir
    on cw.student_number = ir.student_id
    and cw.academic_year = ir.academic_year_int
    and cw.iready_subject = ir.subject
    and cw._dbt_source_project = ir._dbt_source_project
    and rt.region = ir.region
    and rt.name = ir.test_round
    and ir.rn_subj_round = 1
left join
    deduplicate as d
    on cw.student_number = d.student_id
    and cw.academic_year = d.academic_year_int
    and cw.iready_subject = d.subject

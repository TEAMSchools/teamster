with
    subjects as (
        select 'Reading' as iready_subject, 'ENG' as ps_credittype,
        union all
        select 'Math' as iready_subject, 'MATH' as ps_credittype,
    ),

    star as (
        select
            s.student_identifier as student_number,
            s.district_benchmark_category_level,
            s.district_benchmark_category_name,
            s.district_benchmark_proficient,
            s.scaled_score,
            s.current_sgp,
            s.completed_date,

            d.domain_name,
            d.standard_name,
            d.standard_description,
            d.standard_mastery_level,
            d.standard_percent_mastery,

            case
                when s._dagster_partition_subject = 'SR'
                then 'Reading'
                when s._dagster_partition_subject = 'SM'
                then 'Math'
                when s._dagster_partition_subject = 'SEL'
                then 'Early Literacy'
            end as subject,
            case
                when s.screening_period_window_name = 'Fall'
                then 'BOY'
                when s.screening_period_window_name = 'Winter'
                then 'MOY'
                when s.screening_period_window_name = 'Spring'
                then 'EOY'
            end as administration_window,

            row_number() over (
                partition by
                    s.student_identifier,
                    s._dagster_partition_subject,
                    s.screening_period_window_name
                order by s.completed_date desc
            ) as rn_subject_round,
        from {{ ref("stg_renlearn__star") }} as s
        left join
            {{ ref("stg_renlearn__star_dashboard_standards") }} as d
            on s.assessment_id = d.assessment_id
    ),

    iready_unpivot as (
        select
            student_id,
            subject,
            academic_year_int,
            start_date,
            completion_date,
            domain_name,
            relative_placement,
        from
            {{ ref("stg_iready__diagnostic_results") }} unpivot (
                relative_placement for domain_name in (
                    phonics_relative_placement,
                    algebra_and_algebraic_thinking_relative_placement,
                    geometry_relative_placement,
                    measurement_and_data_relative_placement,
                    number_and_operations_relative_placement,
                    high_frequency_words_relative_placement,
                    phonological_awareness_relative_placement,
                    reading_comprehension_informational_text_relative_placement,
                    reading_comprehension_literature_relative_placement,
                    reading_comprehension_overall_relative_placement,
                    vocabulary_relative_placement,
                    comprehension_informational_text_relative_placement,
                    comprehension_literature_relative_placement,
                    comprehension_overall_relative_placement
                )
            )
    )

select
    co.student_number,
    co.lastfirst as student_name,
    co.grade_level,
    co.school_abbreviation as school,
    co.lep_status,
    co.gender,
    co.ethnicity as race_ethnicity,
    co.advisory_name as advisory,

    subj.iready_subject,
    subj.ps_credittype,

    ar as administration_round,

    ir.start_date,
    ir.completion_date,
    ir.rush_flag,
    ir.overall_relative_placement,
    ir.placement_3_level,
    ir.overall_scale_score,
    ir.percent_progress_to_annual_typical_growth_percent as progress_to_typical,
    ir.percent_progress_to_annual_stretch_growth_percent as progress_to_stretch,

    s.district_benchmark_category_level as star_category_level,
    s.district_benchmark_category_name as star_category_name,
    s.district_benchmark_proficient as star_proficient,
    s.scaled_score,
    s.current_sgp,
    s.completed_date,
    s.domain_name as star_domain,
    s.standard_name,
    s.standard_description,
    s.standard_mastery_level,
    s.standard_percent_mastery,
    s.rn_subject_round,

    up.domain_name,
    up.relative_placement,

    e.courses_course_name as course_name,
    e.sections_section_number as section_number,
    e.teacher_lastfirst as teacher_name,

    case when co.spedlep like 'SPED%' then 'Has IEP' else 'No IEP' end as iep_status,
from {{ ref("base_powerschool__student_enrollments") }} as co
cross join subjects as subj
cross join unnest(['BOY', 'MOY', 'EOY']) as ar
left join
    {{ ref("base_iready__diagnostic_results") }} as ir
    on co.student_number = ir.student_id
    and co.academic_year = ir.academic_year_int
    and subj.iready_subject = ir.subject
    and ar = ir.test_round
    and ir.rn_subj_round = 1
left join
    iready_unpivot as up
    on ir.student_id = up.student_id
    and ir.academic_year_int = up.academic_year_int
    and ir.subject = up.subject
    and ir.start_date = up.start_date
    and ir.completion_date = up.completion_date
left join
    star as s
    on co.student_number = s.student_number
    and subj.iready_subject = s.subject
    and ar = s.administration_window
left join
    {{ ref("base_powerschool__course_enrollments") }} as e
    on co.student_number = e.students_student_number
    and co.academic_year = e.cc_academic_year
    and subj.ps_credittype = e.courses_credittype
    and not e.is_dropped_section
    and e.rn_credittype_year = 1
where
    co.academic_year = 2023
    and co.rn_year = 1
    and co.enroll_status = 0
    and co.region = 'Miami'
    and co.grade_level < 3

with
    subjects as (
        select 'Reading' as iready_subject, 'ENG' as ps_credittype,

        union all

        select 'Math' as iready_subject, 'MATH' as ps_credittype,
    ),

    sub as (
        select
            student_identifier as student_number,
            _dagster_partition_subject as star_subject,
            state_benchmark_category_level,
            state_benchmark_category_name,
            state_benchmark_proficient,
            scaled_score,
            unified_score,
            current_sgp,
            completed_date,
            assessment_id,
            assessment_number,
            assessment_status,

            _dagster_partition_fiscal_year - 1 as academic_year,

            case
                _dagster_partition_subject
                when 'SR'
                then 'Reading'
                when 'SM'
                then 'Math'
                when 'SEL'
                then 'Reading'
            end as `subject`,

            case
                screening_period_window_name
                when 'Fall'
                then 'BOY'
                when 'Winter'
                then 'MOY'
                when 'Spring'
                then 'EOY'
            end as administration_window,

            row_number() over (
                partition by
                    student_identifier,
                    _dagster_partition_subject,
                    screening_period_window_name,
                    _dagster_partition_fiscal_year
                order by completed_date desc
            ) as rn_subject_round,
        from {{ ref("stg_renlearn__star") }}
        where deactivation_reason is null
    ),

    star as (
        select
            sub.academic_year,
            sub.student_number,
            sub.state_benchmark_category_level,
            sub.state_benchmark_category_name,
            sub.state_benchmark_proficient,
            sub.scaled_score,
            sub.unified_score,
            sub.current_sgp,
            sub.completed_date,
            sub.assessment_id,
            sub.assessment_number,
            sub.assessment_status,
            sub.subject,
            sub.star_subject,
            sub.administration_window,

            d.domain_name,
            d.domain_mastery_level,
            d.domain_percent_mastery,
            d.standard_name,
            d.standard_description,
            d.standard_mastery_level,
            d.standard_percent_mastery,

            row_number() over (
                partition by
                    sub.student_number,
                    sub.subject,
                    sub.administration_window,
                    sub.academic_year
                order by d.standard_name desc
            ) as rn_subject_round_star,
        from sub
        left join
            {{ ref("stg_renlearn__star_dashboard_standards") }} as d
            on sub.assessment_id = d.assessment_id
        where sub.rn_subject_round = 1
    )

select
    co.academic_year,
    co.student_number,
    co.lastfirst as student_name,
    co.grade_level,
    co.school_abbreviation as school,
    co.lep_status,
    co.gender,
    co.ethnicity as race_ethnicity,
    co.advisory_name as advisory,
    co.spedlep as iep_status,

    subj.iready_subject,
    subj.ps_credittype,

    administration_round,

    e.courses_course_name as course_name,
    e.sections_section_number as section_number,
    e.teacher_lastfirst as teacher_name,

    s.state_benchmark_category_level as star_category_level,
    s.state_benchmark_category_name as star_category_name,
    s.state_benchmark_proficient as star_proficient,
    s.scaled_score,
    s.unified_score,
    s.current_sgp,
    s.completed_date,
    s.domain_name as star_domain,
    s.domain_percent_mastery,
    s.standard_name,
    s.standard_description,
    s.standard_mastery_level,
    s.standard_percent_mastery,
    s.star_subject,
    s.rn_subject_round_star,
from {{ ref("base_powerschool__student_enrollments") }} as co
cross join subjects as subj
cross join unnest(['BOY', 'MOY', 'EOY']) as administration_round
left join
    {{ ref("base_powerschool__course_enrollments") }} as e
    on co.student_number = e.students_student_number
    and co.academic_year = e.cc_academic_year
    and subj.ps_credittype = e.courses_credittype
    and not e.is_dropped_section
    and e.rn_credittype_year = 1
left join
    star as s
    on co.student_number = s.student_number
    and co.academic_year = s.academic_year
    and subj.iready_subject = s.subject
    and administration_round = s.administration_window
where
    co.academic_year = {{ var("current_academic_year") }}
    and co.rn_year = 1
    and co.enroll_status = 0
    and co.region = 'Miami'
    and co.grade_level < 3

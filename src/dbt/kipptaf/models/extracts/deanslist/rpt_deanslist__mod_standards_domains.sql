with
    response_rollup as (
        select
            sr.powerschool_student_number,
            sr.academic_year,
            sr.term_administered,
            sr.percent_correct,
            if(
                sr.subject_area = 'Writing', 'Text Study', sr.subject_area
            ) as subject_area,

            st.standard_domain,
        from {{ ref("int_assessments__response_rollup") }} as sr
        inner join
            {{ ref("stg_assessments__standard_domains") }} as st
            on sr.response_type_code = st.standard_code
        where
            sr.response_type = 'standard'
            and sr.is_internal_assessment
            and sr.academic_year = {{ var("current_academic_year") }}
            and sr.subject_area in ('Text Study', 'Mathematics', 'Writing')
            and sr.module_type in ('QA', 'MQQ')
            and sr.powerschool_student_number in (
                select student_number
                from {{ ref("stg_powerschool__students") }}
                where
                    grade_level < 5
                    and not regexp_contains(_dbt_source_relation, r'kippmiami')
            )
    ),

    standard_avg as (
        select
            powerschool_student_number,
            academic_year,
            term_administered,
            subject_area,
            standard_domain,
            round(avg(percent_correct), 0) as avg_percent_correct,
        from response_rollup
        group by
            powerschool_student_number,
            academic_year,
            term_administered,
            subject_area,
            standard_domain
    )

select
    powerschool_student_number as local_student_id,
    academic_year,
    term_administered,
    subject_area,
    standard_domain,
    avg_percent_correct,
    case
        when avg_percent_correct >= 85
        then 'Exceeds Expectations'
        when avg_percent_correct >= 70
        then 'Met Expectations'
        when avg_percent_correct >= 50
        then 'Approaching Expectations'
        when avg_percent_correct >= 30
        then 'Below Expectations'
        when avg_percent_correct >= 0
        then 'Far Below Expectations'
    end as performance_level,
from standard_avg

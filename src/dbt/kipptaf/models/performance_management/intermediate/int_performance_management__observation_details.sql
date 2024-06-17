
    observation_details as (
        select
            m.employee_number,
            m.observer_employee_number,
            m.observation_id,
            m.teacher_id,
            m.form_long_name,
            m.rubric_id,
            m.observed_at,
            m.glows,
            m.grows,
            m.score_measurement_id,
            m.row_score_value,
            od.row_score_value as locked_row_score,
            m.measurement_name,
            m.text_box,
            m.score_measurement_type,
            m.score_measurement_shortname,
            m.observation_type,
            /*replace with measurementGroup average*/
            sp.etr_score,
            /*replace with measurementGroup average*/
            sp.so_score,
            t.code as form_term,
            t.type as form_type,
            t.academic_year,
            if(
                m.observed_at >= date(2023, 07, 01), sp.overall_score, m.overall_score
            ) as overall_score,
            od.overall_score as locked_overall_score,
        from measurements as m
        inner join
            {{ ref("stg_reporting__terms") }} as t
            on regexp_contains(m.form_long_name, t.name)
            and m.observed_at between t.start_date and t.end_date
            and t.lockbox_date
            between m.last_modified_date and m.last_modified_date_lead
        left join
            {{ ref("stg_performance_management__observation_details") }} as od
            on m.observation_id = od.observation_id
            and m.score_measurement_id = od.score_measurement_id
        left join pm_overall_scores_pivot as sp on m.observation_id = sp.observation_id

        union all

        select
            employee_number,
            observer_employee_number,
            observation_id,
            null as teacher_id,
            form_long_name,
            rubric_id,
            observed_at,
            null as glows,
            null as grows,
            measurement_name as score_measurement_id,
            row_score_value,
            row_score_value as locked_row_score,
            measurement_name,
            null as text_box,
            score_type as score_measurement_type,
            measurement_name as score_measurement_shortname,
            etr_score,
            so_score,
            form_term,
            'PM' as form_type,
            academic_year,
            overall_score,
            overall_score as locked_overall_score,
        from {{ ref("int_performance_management__scores_archive") }}
    )

select
    employee_number,
    observer_employee_number,
    observation_id,
    teacher_id,
    form_long_name,
    rubric_id,
    observed_at,
    glows,
    grows,
    score_measurement_id,
    row_score_value,
    locked_row_score,
    measurement_name,
    text_box,
    score_measurement_type,
    score_measurement_shortname,
    etr_score,
    so_score,
    overall_score,
    locked_overall_score,
    form_term,
    form_type,
    academic_year,

    case
        when academic_year >= 2023 and form_type = 'PM'
        then
            row_number() over (
                partition by rubric_id, form_term, employee_number, score_measurement_id
                order by observed_at desc
            )
        when academic_year < 2023 and form_type = 'PM'
        then 1
    end as rn_submission,
from observation_details

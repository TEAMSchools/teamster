with
    measurements as (
        select
            u.internal_id as employee_number,
            u2.internal_id as observer_employee_number,
            o.observation_id,
            o.teacher_id,
            o.rubric_name as form_long_name,
            o.rubric_id,
            o.score as overall_score,
            safe_cast(o.observed_at as date) as observed_at,
            array_to_string(o.list_two_column_a, '|') as glows,
            array_to_string(o.list_two_column_b, '|') as grows,

            ohos.measurement as score_measurement_id,
            ohos.value_score as row_score_value,
            ohos.last_modified_date,
            ohos.last_modified_date_lead,

            m.name as measurement_name,
            regexp_extract(lower(m.name), r'(^.*?)\-') as score_measurement_type,
            regexp_extract(lower(m.name), r'(^.*?):') as score_measurement_shortname,

            regexp_replace(
                regexp_replace(b.value, r'<[^>]*>', ''), r'&nbsp;', ' '
            ) as text_box,

        from {{ ref("stg_schoolmint_grow__observations") }} as o
        inner join
            {{ ref("stg_schoolmint_grow__users") }} as u on o.teacher_id = u.user_id
        inner join
            {{ ref("stg_schoolmint_grow__users") }} as u2 on o.observer_id = u2.user_id
        left join
            {{ ref("stg_schoolmint_grow__observations_history__observation_scores") }}
            as ohos
            on o.observation_id = ohos.observation_id
        left join
            {{ ref("stg_schoolmint_grow__measurements") }} as m
            on ohos.measurement = m.measurement_id
        left join
            {{
                ref(
                    "stg_schoolmint_grow__observations__observation_scores__text_boxes"
                )
            }} as b
            on ohos.observation_id = b.observation_id
            and ohos.measurement = b.measurement
        where
            o.is_published
            /* 2023 is first year with new rubric*/
            and safe_cast(o.observed_at as date) >= date(2023, 07, 01)
    ),
    /* for 2024, move 2023 scores to archive view and delete these CTEs to use calculated overall scores from SMG */
    pm_overall_scores_avg as (
        select
            observation_id,
            score_measurement_type,

            avg(row_score_value) as score_measurement_score,
        from measurements
        where score_measurement_type in ('etr', 's&o')
        group by observation_id, score_measurement_type
    ),

    pm_overall_scores_pivot as (
        select
            p.observation_id,
            p.etr as etr_score,
            p.so as so_score,
            coalesce((0.8 * p.etr) + (0.2 * p.so), p.etr, p.so) as overall_score,
        from
            pm_overall_scores_avg pivot (
                avg(score_measurement_score) for score_measurement_type
                in ('etr', 's&o' as `so`)
            ) as p
    ),

    observation_details as (
        select
            m.employee_number,
            safe_cast(m.observer_employee_number as int) as observer_employee_number,
            m.observation_id,
            m.teacher_id,
            m.form_long_name,
            m.rubric_id,
            m.observed_at,
            m.glows,
            m.grows,
            m.score_measurement_id,
            m.row_score_value,
            m.measurement_name,
            m.text_box,
            m.score_measurement_type,
            m.score_measurement_shortname,
            sp.etr_score,
            sp.so_score,
            if(
                m.observed_at <= date(2023, 07, 01), sp.overall_score, m.overall_score
            ) as overall_score,
            t.code as form_term,
            t.type as form_type,
            t.academic_year as academic_year,
        from measurements as m
        left join pm_overall_scores_pivot as sp on m.observation_id = sp.observation_id
        left join
            {{ ref("stg_reporting__terms") }} as t
            on regexp_contains(m.form_long_name, t.name)
            and m.observed_at between t.start_date and t.end_date
            and t.lockbox_date
            between m.last_modified_date and m.last_modified_date_lead

        union all
        select
            sa.employee_number,
            sa.observer_employee_number,
            'archive' as observation_id,
            null as teacher_id,
            sa.form_long_name,
            concat(sa.academic_year, sa.form_term) as rubric_id,
            sa.observed_at,
            null as glows,
            null as grows,
            sa.measurement_name as score_measurement_id,
            sa.row_score_value,
            sa.measurement_name,
            null as text_box,
            sa.score_type as score_measurement_type,
            sa.measurement_name as score_measurement_shortname,
            sa.etr_score,
            sa.so_score,
            sa.overall_score,
            sa.form_term,
            'PM' as form_type,
            sa.academic_year,
        from {{ ref("int_performance_management__scores_archive") }} as sa
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
    measurement_name,
    text_box,
    score_measurement_type,
    score_measurement_shortname,
    etr_score,
    so_score,
    overall_score,
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
        else null
    end as rn_submission,
from observation_details

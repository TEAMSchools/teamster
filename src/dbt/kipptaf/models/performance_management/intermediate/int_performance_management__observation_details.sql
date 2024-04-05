with
    scaffold as (
        select
            ur.user_id,
            ur.role_name,

            u.internal_id_int as internal_id,

            rt.type as form_type,
            rt.code as form_term,
            rt.name as form_short_name,
            rt.start_date,
            rt.end_date,
            rt.academic_year,
        from {{ ref("stg_schoolmint_grow__users__roles") }} as ur
        inner join
            {{ ref("stg_schoolmint_grow__users") }} as u on ur.user_id = u.user_id
        inner join
            {{ ref("stg_reporting__terms") }} as rt on ur.role_name = rt.grade_band
        where ur.role_name = 'Teacher'
    ),

    observations as (
        select
            o.observation_id,
            o.teacher_id,
            o.rubric_name as form_long_name,
            o.created,
            o.observer_name,
            o.observer_email,
            o.score as overall_score,
            safe_cast(o.observed_at as date) as observed_at,

            case
                when o.rubric_name like '%Coaching%'
                then 'PM'
                when o.rubric_name like '%Walkthrough%'
                then 'WT'
                when o.rubric_name like '%O3%'
                then 'O3'
            end as form_type,

            case
                when
                    o.rubric_name = 'Coaching Tool: Coach ETR and Reflection'
                    and safe_cast(
                        o.observed_at as date
                    ) between date({{ var("current_academic_year") }}, 7, 1) and date(
                        {{ var("current_academic_year") }}, 10, 31
                    )
                then 'BOY (Coach)'
                when
                    o.rubric_name = 'Coaching Tool: Teacher Reflection'
                    and safe_cast(
                        o.observed_at as date
                    ) between date({{ var("current_academic_year") }}, 7, 1) and date(
                        {{ var("current_academic_year") }}, 10, 31
                    )
                then 'BOY (Self)'
                when
                    o.rubric_name = 'Coaching Tool: Coach ETR and Reflection'
                    and safe_cast(
                        o.observed_at as date
                    ) between date({{ var("current_academic_year") }}, 11, 1) and (
                        date({{ var("current_fiscal_year") }}, 3, 1) - 1
                    )
                then 'MOY (Coach)'
                when
                    o.rubric_name = 'Coaching Tool: Teacher Reflection'
                    and safe_cast(
                        o.observed_at as date
                    ) between date({{ var("current_academic_year") }}, 11, 1) and (
                        date({{ var("current_fiscal_year") }}, 3, 1) - 1
                    )
                then 'MOY (Self)'
                when
                    o.rubric_name = 'Coaching Tool: Coach ETR and Reflection'
                    and safe_cast(
                        o.observed_at as date
                    ) between date({{ var("current_fiscal_year") }}, 3, 1) and date(
                        {{ var("current_fiscal_year") }}, 6, 30
                    )
                then 'EOY (Coach)'
                when
                    o.rubric_name = 'Coaching Tool: Teacher Reflection'
                    and safe_cast(
                        o.observed_at as date
                    ) between date({{ var("current_fiscal_year") }}, 3, 1) and date(
                        {{ var("current_fiscal_year") }}, 6, 30
                    )
                then 'EOY (Self)'
            end as form_short_name,

            array_to_string(o.list_two_column_a, '|') as glows,
            array_to_string(o.list_two_column_b, '|') as grows,

            safe_cast(u.internal_id as int) as observer_employee_number,
        from {{ ref("stg_schoolmint_grow__observations") }} as o
        inner join
            {{ ref("stg_schoolmint_grow__users") }} as u on o.observer_id = u.user_id
        inner join
            {{ ref("stg_schoolmint_grow__users__roles") }} as ur
            on u.user_id = ur.user_id
            and ur.role_name not like '%Teacher%'
        where
            o.is_published
            /* 2023 is first year with new rubric */
            and o.observed_at >= timestamp(date(2023, 7, 1))
            /* remove self coaching observations*/
            and not (
                o.rubric_name = 'Coaching Tool: Coach ETR and Reflection'
                and o.teacher_id = o.observer_id
            )
    ),

    observation_measurements as (
        select
            o.observation_id,
            o.teacher_id,
            o.form_long_name,
            o.created,
            o.observed_at,
            o.observer_name,
            o.observer_email,
            o.observer_employee_number,
            o.overall_score,
            o.form_short_name,
            o.form_type,
            o.glows,
            o.grows,

            os.measurement as score_measurement_id,
            os.percentage as score_percentage,
            os.value_score as row_score_value,

            m.name as measurement_name,
            m.scale_min as measurement_scale_min,
            m.scale_max as measurement_scale_max,

            regexp_replace(
                regexp_replace(b.value, r'<[^>]*>', ''), r'&nbsp;', ' '
            ) as text_box,

            regexp_extract(lower(m.name), r'(^.*?)\-') as score_measurement_type,
            regexp_extract(lower(m.name), r'(^.*?):') as score_measurement_shortname,
        from observations as o
        left join
            {{ ref("stg_schoolmint_grow__observations__observation_scores") }} as os
            on o.observation_id = os.observation_id
        left join
            {{ ref("stg_schoolmint_grow__measurements") }} as m
            on os.measurement = m.measurement_id
        left join
            {{
                ref(
                    "stg_schoolmint_grow__observations__observation_scores__text_boxes"
                )
            }} as b
            on os.observation_id = b.observation_id
            and os.measurement = b.measurement
    ),

    pm_overall_scores_avg as (
        select
            observation_id,
            score_measurement_type,

            avg(row_score_value) as score_measurement_score,
        from observation_measurements
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
            s.user_id,
            s.role_name,
            s.internal_id,
            s.form_type,
            s.form_term,
            s.form_short_name,
            s.start_date,
            s.end_date,
            s.academic_year,

            o.score_measurement_type,
            o.score_measurement_shortname,
            o.observation_id,
            o.teacher_id,
            o.form_long_name,
            o.created,
            o.observed_at,
            o.observer_name,
            o.observer_employee_number,
            o.overall_score,
            o.glows,
            o.grows,
            o.score_measurement_id,
            o.score_percentage,
            o.row_score_value,
            o.measurement_name,
            o.measurement_scale_min,
            o.measurement_scale_max,
            o.text_box,

            'ETR + S&O' as score_type,

            row_number() over (
                partition by
                    s.form_type,
                    s.form_short_name,
                    s.internal_id,
                    o.score_measurement_id
                order by o.observed_at desc
            ) as rn_submission,
        from scaffold as s
        left join
            observation_measurements as o
            on o.observed_at between s.start_date and s.end_date
            /* Matches on name for PM Rounds to distinguish Self and Coach */
            and s.form_short_name = o.form_short_name
            and s.user_id = o.teacher_id
        where s.form_type = 'PM'

        union all

        select
            s.user_id,
            s.role_name,
            s.internal_id,
            s.form_type,
            s.form_term,
            s.form_short_name,
            s.start_date,
            s.end_date,
            s.academic_year,

            o.score_measurement_type,
            o.score_measurement_shortname,
            o.observation_id,
            o.teacher_id,
            o.form_long_name,
            o.created,
            o.observed_at,
            o.observer_name,
            o.observer_employee_number,
            o.overall_score,
            o.glows,
            o.grows,
            o.score_measurement_id,
            o.score_percentage,
            o.row_score_value,
            o.measurement_name,
            o.measurement_scale_min,
            o.measurement_scale_max,
            o.text_box,

            safe_cast(null as string) as score_type,

            row_number() over (
                partition by
                    s.form_type,
                    s.form_short_name,
                    s.internal_id,
                    o.score_measurement_id
                order by o.observed_at desc
            ) as rn_submission,
        from scaffold as s
        left join
            observation_measurements as o
            on o.observed_at between s.start_date and s.end_date
            /* matches only on type and date for weekly forms */
            and s.form_type = o.form_type
            and s.user_id = o.teacher_id
        where s.form_type in ('WT', 'O3')
    ),

    all_data as (
        select
            od.user_id,
            od.role_name,
            od.internal_id,
            od.form_type,
            od.form_term,
            od.form_short_name,
            od.form_long_name,
            od.score_type,
            od.score_measurement_type,
            od.score_measurement_shortname,
            od.start_date,
            od.end_date,
            od.academic_year,
            od.observation_id,
            od.teacher_id,
            od.created,
            od.observed_at,
            od.observer_name,
            od.observer_employee_number,
            od.glows,
            od.grows,
            od.score_measurement_id,
            od.score_percentage,
            od.row_score_value,
            od.measurement_name,
            od.text_box,
            od.rn_submission,

            os.etr_score,
            os.so_score,

            /* 2023 direct SMG overall score is messed up */
            if(
                od.academic_year <= 2023, os.overall_score, od.overall_score
            ) as overall_score,
        from observation_details as od
        left join pm_overall_scores_pivot as os on od.observation_id = os.observation_id
        where od.rn_submission = 1

        union all

        select
            null as user_id,
            null as role_name,

            employee_number as internal_id,

            'PM' as form_type,

            form_term,
            form_short_name,
            form_long_name,
            score_type,

            null as score_measurement_type,
            null as score_measurement_shortname,
            null as start_date,
            null as end_date,

            academic_year,

            null as observation_id,
            null as teacher_id,
            null as created,

            observed_at,
            observer_name,
            observer_employee_number,

            null as glows,
            null as grows,
            null as score_measurement_id,
            null as score_percentage,

            row_score_value,
            measurement_name,

            null as text_box,

            1 as rn_submission,

            etr_score,
            so_score,
            overall_score,
        from {{ ref("int_performance_management__scores_archive") }}
    )

select
    user_id,
    role_name,
    internal_id,
    form_type,
    form_term,
    form_short_name,
    form_long_name,
    score_type,
    score_measurement_type,
    score_measurement_shortname,
    start_date,
    end_date,
    academic_year,
    observation_id,
    teacher_id,
    created,
    observed_at,
    observer_name,
    observer_employee_number,
    etr_score,
    so_score,
    overall_score,
    glows,
    grows,
    score_measurement_id,
    score_percentage,
    row_score_value,
    measurement_name,
    text_box,
    rn_submission,

    case
        when etr_score >= 3.5
        then 4
        when etr_score >= 2.745
        then 3
        when etr_score >= 1.745
        then 2
        when etr_score < 1.75
        then 1
    end as etr_tier,
    case
        when so_score >= 3.5
        then 4
        when so_score >= 2.945
        then 3
        when so_score >= 1.945
        then 2
        when so_score < 1.95
        then 1
    end as so_tier,
    case
        when overall_score >= 3.5
        then 4
        when overall_score >= 2.745
        then 3
        when overall_score >= 1.745
        then 2
        when overall_score < 1.75
        then 1
    end as overall_tier,
from all_data

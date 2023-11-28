with
    scaffold as (
        select
            ur.user_id,
            ur.role_name,

            u.internal_id,

            rt.type as form_type,
            rt.code as form_term,
            rt.name as form_short_name,
            rt.start_date,
            rt.end_date,
            rt.academic_year,

            sr.employee_number,
            sr.preferred_name_lastfirst as teammate,
            sr.business_unit_home_name as entity,
            sr.home_work_location_name as location,
            sr.home_work_location_grade_band as grade_band,
            sr.home_work_location_powerschool_school_id,
            sr.department_home_name as department,
            sr.primary_grade_level_taught as grade_taught,
            sr.job_title,
            sr.report_to_preferred_name_lastfirst as manager,
            sr.worker_original_hire_date,
            sr.assignment_status,
        from {{ ref("stg_schoolmint_grow__users__roles") }} as ur
        left join {{ ref("stg_schoolmint_grow__users") }} as u on ur.user_id = u.user_id
        left join
            {{ ref("stg_reporting__terms") }} as rt on ur.role_name = rt.grade_band
        left join
            {{ ref("base_people__staff_roster") }} as sr
            on u.internal_id = safe_cast(sr.employee_number as string)
        where ur.role_name like '%Teacher%'
    ),

    boxes as (
        select
            observation_id,
            measurement,
            `value` as text_box_value,
            null as checkbox_value,
            'textbox' as question_type,
        from
            {{
                ref(
                    "stg_schoolmint_grow__observations__observation_scores__text_boxes"
                )
            }}
    ),

    observations as (
        select
            observation_id,
            teacher_id,
            rubric_name as form_long_name,
            created,
            observer_name,
            observer_email,
            score as overall_score,
            safe_cast(observed_at as date) as observed_at,

            case
                when rubric_name like '%Coaching%'
                then 'PM'
                when rubric_name like '%Walkthrough%'
                then 'WT'
                when rubric_name like '%O3%'
                then 'O3'
            end as form_type,

            case
                when lower(rubric_name) not like '%etr%'
                then null
                when score < 1.75
                then 1
                when score >= 1.75 and score < 2.75
                then 2
                when score >= 2.75 and score < 3.5
                then 3
                when score > 3.5
                then 4
            end as tier,

            case
                when
                    rubric_name = 'Coaching Tool: Coach ETR and Reflection'
                    and safe_cast(
                        observed_at as date
                    ) between date({{ var("current_academic_year") }}, 7, 1) and date(
                        {{ var("current_academic_year") }}, 10, 31
                    )
                then 'BOY (Coach)'
                when
                    rubric_name = 'Coaching Tool: Teacher Reflection'
                    and safe_cast(
                        observed_at as date
                    ) between date({{ var("current_academic_year") }}, 7, 1) and date(
                        {{ var("current_academic_year") }}, 10, 31
                    )
                then 'BOY (Self)'
                when
                    rubric_name = 'Coaching Tool: Coach ETR and Reflection'
                    and safe_cast(
                        observed_at as date
                    ) between date({{ var("current_academic_year") }}, 11, 1) and (
                        date({{ var("current_fiscal_year") }}, 3, 1) - 1
                    )
                then 'MOY (Coach)'
                when
                    rubric_name = 'Coaching Tool: Teacher Reflection'
                    and safe_cast(
                        observed_at as date
                    ) between date({{ var("current_academic_year") }}, 11, 1) and (
                        date({{ var("current_fiscal_year") }}, 3, 1) - 1
                    )
                then 'MOY (Self)'
                when
                    rubric_name = 'Coaching Tool: Coach ETR and Reflection'
                    and safe_cast(
                        observed_at as date
                    ) between date({{ var("current_fiscal_year") }}, 3, 1) and date(
                        {{ var("current_fiscal_year") }}, 6, 30
                    )
                then 'EOY (Coach)'
                when
                    rubric_name = 'Coaching Tool: Teacher Reflection'
                    and safe_cast(
                        observed_at as date
                    ) between date({{ var("current_fiscal_year") }}, 3, 1) and date(
                        {{ var("current_fiscal_year") }}, 6, 30
                    )
                then 'EOY (Self)'
            end as form_short_name,

            array_to_string(list_two_column_a, '|') as glows,
            array_to_string(list_two_column_b, '|') as grows,
        from {{ ref("stg_schoolmint_grow__observations") }}
        where
            is_published
            /* 2023 is first year with new rubric */
            and observed_at >= timestamp(date(2023, 7, 1))
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
            o.overall_score,
            o.form_short_name,
            o.form_type,
            o.tier,
            o.glows,
            o.grows,

            os.measurement as score_measurement_id,

            os.percentage as score_percentage,
            os.value_score as row_score_value,

            m.name as measurement_name,
            m.scale_min as measurement_scale_min,
            m.scale_max as measurement_scale_max,

            regexp_replace(
                regexp_replace(b.text_box_value, r'<[^>]*>', ''), r'&nbsp;', ' '
            ) as text_box,
        from observations as o
        left join
            {{ ref("stg_schoolmint_grow__observations__observation_scores") }} as os
            on o.observation_id = os.observation_id
        left join
            {{ ref("stg_schoolmint_grow__measurements") }} as m
            on os.measurement = m.measurement_id
        left join
            boxes as b
            on os.observation_id = b.observation_id
            and os.measurement = b.measurement
    )

   -- observation_details as (
        select
            s.user_id,
            s.role_name,
            s.internal_id,
            s.form_type,
            s.form_term,
            'ETR + S&O' as score_type,
            s.form_short_name,
            s.start_date,
            s.end_date,
            s.academic_year,
            s.employee_number,
            s.teammate,
            s.entity,
            s.location,
            s.grade_band,
            s.home_work_location_powerschool_school_id,
            s.department,
            s.grade_taught,
            s.job_title,
            s.manager,
            s.worker_original_hire_date,
            s.assignment_status,

            o.observation_id,
            o.teacher_id,
            o.form_long_name,
            o.created,
            o.observed_at,
            o.observer_name,
            o.overall_score,
            o.glows,
            o.grows,
            o.score_measurement_id,
            o.score_percentage,
            o.row_score_value,
            o.measurement_name,
            o.measurement_scale_min,
            o.measurement_scale_max,
            o.tier,
            o.text_box,

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
            and s.form_type = 'PM'
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

            case
                when
                    os.measurement in (
                        '6484981d725ca60011b15280',
                        '648499ab0b57a8001189bea8',
                        '64849b290bd6de00117a7dc9',
                        '64849b7f725ca60011b15ea8',
                        '64849f0bad931f00112e4a46',
                        '6484a223ca819d0011f10745',
                        '6484a22aca819d0011f10776',
                        '6484a230725ca60011b17262',
                        '6484a240ca819d0011f107aa',
                        '6484a2458b403e0011ff4317',
                        '6484a24a0bd6de00117a8fe9',
                        '6484a2580bd6de00117a8ff3',
                        '6484a25dad931f00112e51ae',
                        '6484a2648b403e0011ff437a',
                        '6484a26f0bd6de00117a905c',
                        '6484a2778b403e0011ff43b9',
                        '6484a2a98b403e0011ff4488',
                        '6484a2b08b403e0011ff44aa',
                        '64c951fef1e9ad0011f4fd03'
                    )
                then 'ETR'
                when
                    os.measurement in (
                        '6484c4fb725ca60011b1bc92',
                        '6484c500725ca60011b1bc98',
                        '64a7237b0c348e0011c51727',
                        '64a7238955032e001180cbc0',
                        '64a720f6f27af600114e0046',
                        '64a7233fc3a17300119ca37b',
                        '64be9eea9c918a001163ffd0',
                        '64be9d7dff1c61001190d165',
                        '64a7236d353ba70011ce2c43',
                        '64a722ca7ee3cf001117edef'
                    )
                then 'SO'
                else null
            end as score_measurement_type,

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
    ),
     pm_overall_scores_long as (
        select
            om.observation_id,
            om.score_measurement_type,
            avg(om.row_score_value) as score_measurement_score
        from observation_measurements as om
        WHERE om.score_measurement_type IN ('ETR','SO')
        group by om.observation_id, om.score_measurement_type

     ),
     pm_overall_scores as (
        select
            p.observation_id,
            p.ETR as etr_score,
            p.SO as so_score,
            coalesce((0.8 * p.ETR) + (0.2 * p.SO), p.ETR, p.SO) as overall_score
        from
            pm_overall_scores_long pivot (
                avg(score_measurement_score) for score_measurement_type
                in ('ETR', 'SO')
            ) as p
    ), 

    observation_details as (
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
        where s.form_type = 'PM'

        union all

        select
            s.user_id,
            s.role_name,
            s.internal_id,
            s.form_type,
            s.form_term,
            safe_cast(null as string) as score_type,
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
            /* matches only on type and date for weekly forms */
            and s.form_type = o.form_type
            and s.user_id = o.teacher_id
        where s.form_type in ('WT', 'O3')
    ),

    historical_overall_scores as (
        select
            s.employee_number,
            s.academic_year,
            s.form_term,
            os.etr_score,
            os.so_score,
            os.overall_score,
            null as etr_tier,
            null as so_tier,
            o.tier,
        from scaffold as s
        left join
            observations as o
            on o.observed_at between s.start_date and s.end_date
            /* Matches on name for PM Rounds to distinguish Self and Coach */
            and s.form_short_name = o.form_short_name
            and s.user_id = o.teacher_id
        left join 
            pm_overall_scores as os
            on o.observation_id = os.observation_id
        where s.form_type = 'PM'

        union all

        select
            employee_number,
            academic_year,
            pm_term as form_term,
            etr_score,
            so_score,
            overall_score,
            etr_tier,
            so_tier,
            overall_tier as tier,
        from
            {{
                source(
                    "performance_management",
                    "src_performance_management__scores_overall_archive",
                )
            }}
    ),

    historical_detail_scores as (
        select
            employee_number,
            academic_year,
            form_term,
            score_type,
            null as observer_employee_number,
            observer_name,
            observed_at,
            measurement_name,
            row_score_value,
        from observation_details
        where form_type = 'PM' and overall_score is not null

        union all

        select
            subject_employee_number as employee_number,
            academic_year,
            pm_term as form_term,
            score_type,
            observer_employee_number,
            null as observer_name,
            safe_cast(observed_at as date) as observed_at,
            measurement_name,
            score_value as row_score_value,
        from
            {{
                source(
                    "performance_management",
                    "src_performance_management__scores_detail_archive",
                )
            }}
    ),

    historical_data as (
        select
            os.employee_number,
            os.academic_year,
            os.form_term,
            os.etr_score,
            os.so_score,
            os.overall_score,
            os.etr_tier,
            os.so_tier,
            os.tier,

            ds.score_type,
            ds.observer_employee_number,
            ds.observer_name,
            ds.observed_at,
            ds.measurement_name,
            ds.row_score_value,

            'Coaching Tools: Coach ETR and Reflection' as form_long_name,

            concat(ds.form_term, ' (Coach)') as form_short_name,
        from historical_overall_scores as os
        inner join
            historical_detail_scores as ds
            on os.employee_number = ds.employee_number
            and os.academic_year = ds.academic_year
            and os.form_term = ds.form_term
    )

select
    user_id,
    od.role_name,
    od.internal_id,
    od.form_type,
    od.form_term,
    od.form_short_name,
    od.form_long_name,
    od.score_type,
    od.start_date,
    od.end_date,
    od.academic_year,
    od.employee_number,
    od.teammate,
    od.entity,
    od.location,
    od.grade_band,
    od.home_work_location_powerschool_school_id,
    od.department,
    od.grade_taught,
    od.job_title,
    od.manager,
    od.worker_original_hire_date,
    od.assignment_status,
    od.observation_id,
    od.teacher_id,
    od.created,
    od.observed_at,
    od.observer_name,
    os.etr_score as etr_score,
    os.so_score as so_score,
    CASE 
      WHEN od.academic_year <= 2024 THEN os.overall_score
      ELSE od.overall_score
    END AS overall_score,
    null as etr_tier,
    null as so_tier,
    od.tier,
    od.glows,
    od.grows,
    od.score_measurement_id,
    od.score_percentage,
    od.row_score_value,
    od.measurement_name,
    od.text_box,
    od.rn_submission,
from observation_details as od
LEFT JOIN pm_overall_scores as os
  on od.observation_id = os.observation_id
where od.rn_submission = 1

union all

select
    null as user_id,
    null as role_name,
    null as internal_id,
    'PM' as form_type,
    hd.form_term,
    hd.form_short_name,
    hd.form_long_name,
    hd.score_type,
    null as start_date,
    null as end_date,
    hd.academic_year,
    hd.employee_number,
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
    null as observation_id,
    null as teacher_id,
    null as created,
    hd.observed_at,
    hd.observer_name,
    hd.etr_score,
    hd.so_score,
    hd.overall_score,
    hd.etr_tier,
    hd.so_tier,
    hd.tier,
    null as glows,
    null as grows,
    null as score_measurement_id,
    null as score_percentage,
    hd.row_score_value,
    hd.measurement_name,
    null as text_box,
    1 as rn_submission,
from historical_data as hd
left join
    {{ ref("base_people__staff_roster_history") }} as sr
    on hd.employee_number = sr.employee_number
    and hd.observed_at
    between safe_cast(sr.work_assignment__fivetran_start as date) and safe_cast(
        sr.work_assignment__fivetran_end as date
    )
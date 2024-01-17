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

            -- sr.employee_number,
            -- sr.preferred_name_lastfirst as teammate,
            -- sr.business_unit_home_name as entity,
            -- sr.home_work_location_name as location,
            -- sr.home_work_location_grade_band as grade_band,
            -- sr.home_work_location_powerschool_school_id,
            -- sr.department_home_name as department,
            -- sr.primary_grade_level_taught as grade_taught,
            -- sr.job_title,
            -- sr.report_to_preferred_name_lastfirst as manager,
            -- sr.worker_original_hire_date,
            -- sr.assignment_status,
            -- sr.mail,
            -- sr.report_to_mail,
            -- sr.sam_account_name,
            -- sr.report_to_sam_account_name,
        from {{ ref("stg_schoolmint_grow__users__roles") }} as ur
        left join {{ ref("stg_schoolmint_grow__users") }} as u on ur.user_id = u.user_id
        left join
            {{ ref("stg_reporting__terms") }} as rt on ur.role_name = rt.grade_band
        -- left join
        --     {{ ref("base_people__staff_roster") }} as sr
        --     on u.internal_id = safe_cast(sr.employee_number as string)
        where ur.role_name like '%Teacher%'
    ),

    observer_details as (
        select ur.user_id, u.internal_id,
        from {{ ref("stg_schoolmint_grow__users__roles") }} as ur
        left join {{ ref("stg_schoolmint_grow__users") }} as u on ur.user_id = u.user_id
        where ur.role_name not like '%Teacher%'
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

            safe_cast(od.internal_id as int) as observer_employee_number,

        from {{ ref("stg_schoolmint_grow__observations") }} as o
        inner join observer_details as od on o.observer_id = od.user_id
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
                regexp_replace(b.text_box_value, r'<[^>]*>', ''), r'&nbsp;', ' '
            ) as text_box,

            regexp_extract(lower(m.name),r'^[^-]*',1,1) as score_measurement_type,

            regexp_extract(lower(m.name),r'^[^:]*',1,1) as score_measurement_shortname,

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
            case when
              om.score_measurement_type = 's&o' then 'so'
              else om.score_measurement_type
            end as om.score_measurement_type,
            avg(om.row_score_value) as score_measurement_score,
        from observation_measurements as om
        where om.score_measurement_type in ('etr', 's&o')
        group by om.observation_id, om.score_measurement_type

    ),

    pm_overall_scores as (
        select
            p.observation_id,
            p.etr as etr_score,
            p.so as so_score,
            coalesce((0.8 * p.etr) + (0.2 * p.so), p.etr, p.so) as overall_score,
        from
            pm_overall_scores_long pivot (
                avg(score_measurement_score) for score_measurement_type in ('etr', 'so')
            ) as p
    ),

    observation_details as (
        select
            s.user_id,
            s.role_name,
            s.internal_id,
            s.type as form_type,
            s.code as form_term,
            s.name as form_short_name,
            s.start_date,
            s.end_date,
            s.academic_year,
            'ETR + S&O' as score_type,

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
            employee_number,
            academic_year,
            pm_term as form_term,
            etr_score,
            so_score,
            overall_score,
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

            ds.score_type,
            ds.observer_employee_number,
            ds.observer_name,
            ds.observed_at,
            ds.measurement_name,
            ds.row_score_value,

            'Coaching Tool: Coach ETR and Reflection' as form_long_name,

            concat(ds.form_term, ' (Coach)') as form_short_name,
        from historical_overall_scores as os
        inner join
            historical_detail_scores as ds
            on os.employee_number = ds.employee_number
            and os.academic_year = ds.academic_year
            and os.form_term = ds.form_term
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
            od.start_date,
            od.end_date,
            od.academic_year,
            od.observation_id,
            od.teacher_id,
            od.created,
            od.observed_at,
            od.observer_name,
            od.observer_employee_number,
            os.etr_score as etr_score,
            os.so_score as so_score,
            case
                when od.academic_year <= 2024
                then os.overall_score
                else od.overall_score
            end as overall_score,
            od.glows,
            od.grows,
            od.score_measurement_id,
            od.score_percentage,
            od.row_score_value,
            od.measurement_name,
            od.text_box,
            od.rn_submission,
        from observation_details as od
        left join pm_overall_scores as os on od.observation_id = os.observation_id
        where od.rn_submission = 1

        union all

        select
            null as `user_id`,
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
            null as observation_id,
            null as teacher_id,
            null as created,
            hd.observed_at,
            hd.observer_name,
            hd.observer_employee_number,
            hd.etr_score,
            hd.so_score,
            hd.overall_score,
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
            {{ ref("base_people__staff_roster") }} as r
            on hd.employee_number = r.employee_number

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

with
    scaffold as (
        select
            ur.user_id,
            ur.role_name,

            u.internal_id,

            rt.type,
            rt.code,
            rt.name,
            rt.start_date,
            rt.end_date,
            rt.academic_year,

            sr.employee_number,
            sr.preferred_name_lastfirst,
            sr.business_unit_home_name,
            sr.home_work_location_name,
            sr.home_work_location_grade_band,
            sr.home_work_location_powerschool_school_id,
            sr.department_home_name,
            sr.primary_grade_level_taught,
            sr.job_title,
            sr.report_to_preferred_name_lastfirst,
            sr.worker_original_hire_date,
            sr.assignment_status,
        from {{ ref("stg_schoolmint_grow__users__roles") }} as ur
        left join {{ ref("stg_schoolmint_grow__users") }} as u on ur.user_id = u.user_id
        left join
            {{ ref("stg_reporting__terms") }} as rt on ur.role_name = rt.grade_band
        left join
            {{ ref("base_people__staff_roster") }} as sr
            on u.internal_id = safe_cast(sr.employee_number as string)
        where ur.role_name != 'Whetstone'
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
            o.rubric_name,
            o.created,
            o.observed_at,
            o.observer_name,
            o.observer_email,
            o.score as overall_score,
            array_to_string(o.list_two_column_a, '|') as glows,
            array_to_string(o.list_two_column_b, '|') as grows,

            os.measurement as score_measurement_id,
            os.percentage as score_percentage,
            os.value_score as row_score_value,

            m.name as measurement_name,
            m.scale_min as measurement_scale_min,
            m.scale_max as measurement_scale_max,

            case
                when o.rubric_name like '%Coaching%'
                then 'PM'
                when o.rubric_name like '%Walkthrough%'
                then 'WT'
                when o.rubric_name like '%O3%'
                then 'O3'
            end as reporting_term_type,
            case
                when lower(o.rubric_name) not like '%etr%'
                then null
                when o.score < 1.75
                then 1
                when o.score >= 1.75 and o.score < 2.75
                then 2
                when o.score >= 2.75 and o.score < 3.5
                then 3
                when o.score > 3.5
                then 4
            end as tier,
            case
                when
                    o.rubric_name = 'Coaching Tool: Coach ETR and Reflection'
                    and date(
                        o.observed_at
                    ) between date({{ var("current_academic_year") }}, 7, 1) and date(
                        {{ var("current_academic_year") }}, 10, 31
                    )
                then 'BOY (Coach)'
                when
                    o.rubric_name = 'Coaching Tool: Teacher Reflection'
                    and date(
                        o.observed_at
                    ) between date({{ var("current_academic_year") }}, 7, 1) and date(
                        {{ var("current_academic_year") }}, 10, 31
                    )
                then 'BOY (Self)'
                when
                    o.rubric_name = 'Coaching Tool: Coach ETR and Reflection'
                    and date(
                        o.observed_at
                    ) between date({{ var("current_academic_year") }}, 11, 1) and date(
                        {{ var("current_academic_year") + 1 }}, 2, 29
                    )
                then 'MOY (Coach)'
                when
                    o.rubric_name = 'Coaching Tool: Teacher Reflection'
                    and date(
                        o.observed_at
                    ) between date({{ var("current_academic_year") }}, 11, 1) and date(
                        {{ var("current_academic_year") + 1 }}, 2, 29
                    )
                then 'MOY (Self)'
                when
                    o.rubric_name = 'Coaching Tool: Coach ETR and Reflection'
                    and date(o.observed_at)
                    between date({{ var("current_academic_year") + 1 }}, 3, 1) and date(
                        {{ var("current_academic_year") + 1 }}, 6, 30
                    )
                then 'EOY (Coach)'
                when
                    o.rubric_name = 'Coaching Tool: Teacher Reflection'
                    and date(o.observed_at)
                    between date({{ var("current_academic_year") + 1 }}, 3, 1) and date(
                        {{ var("current_academic_year") + 1 }}, 6, 30
                    )
                then 'EOY (Self)'
            end as reporting_term_name,

            regexp_replace(
                regexp_replace(b.text_box_value, r'<[^>]*>', ''), r'&nbsp;', ' '
            ) as text_box,
        from {{ ref("stg_schoolmint_grow__observations") }} as o
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
        where
            o.is_published
            and o.observed_at
            >= timestamp(date({{ var("current_academic_year") }}, 7, 1))
    )

select
    s.user_id,
    s.role_name,
    s.internal_id,
    s.type,
    s.code,
    s.name,
    s.start_date,
    s.end_date,
    s.academic_year,
    s.employee_number,
    s.preferred_name_lastfirst,
    s.business_unit_home_name,
    s.home_work_location_name,
    s.home_work_location_grade_band,
    s.home_work_location_powerschool_school_id,
    s.department_home_name,
    s.primary_grade_level_taught,
    s.job_title,
    s.report_to_preferred_name_lastfirst,
    s.worker_original_hire_date,
    s.assignment_status,

    o.observation_id,
    o.teacher_id,
    o.rubric_name,
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
    o.reporting_term_type,
    o.tier,
    o.reporting_term_name,
    o.text_box,

    row_number() over (
        partition by s.type, s.name, s.internal_id, o.score_measurement_id
        order by o.observed_at desc
    ) as rn_submission,
from scaffold as s
left join
    observations as o
    on cast(o.observed_at as date) between s.start_date and s.end_date
    /*
    Matches on name for PM Rounds to distinguish Self and Coach,
    */
    and s.type = 'PM'
    and s.name = o.reporting_term_name
    and s.user_id = o.teacher_id

union all

select
    s.user_id,
    s.role_name,
    s.internal_id,
    s.type,
    s.code,
    s.name,
    s.start_date,
    s.end_date,
    s.academic_year,
    s.employee_number,
    s.preferred_name_lastfirst,
    s.business_unit_home_name,
    s.home_work_location_name,
    s.home_work_location_grade_band,
    s.home_work_location_powerschool_school_id,
    s.department_home_name,
    s.primary_grade_level_taught,
    s.job_title,
    s.report_to_preferred_name_lastfirst,
    s.worker_original_hire_date,
    s.assignment_status,

    o.observation_id,
    o.teacher_id,
    o.rubric_name,
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
    o.reporting_term_type,
    o.tier,
    o.reporting_term_name,
    o.text_box,

    row_number() over (
        partition by s.type, s.name, s.internal_id, o.score_measurement_id
        order by o.observed_at desc
    ) as rn_submission,
from scaffold as s
left join
    observations as o
    on cast(o.observed_at as date) between s.start_date and s.end_date
    /*
    matches only on type and date for weekly forms
    */
    and s.type in ('WT', 'O3')
    and s.type = o.reporting_term_type
    and s.user_id = o.teacher_id

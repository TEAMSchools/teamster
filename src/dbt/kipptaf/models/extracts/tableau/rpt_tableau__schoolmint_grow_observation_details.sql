with
    scaffold as (
        select
            ur.user_id,
            ur.role_name,
            rt.`type`,
            rt.code,
            rt.`name`,
            rt.`start_date`,
            rt.end_date,
            rt.academic_year,
            u.internal_id,
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
        left join
            {{ ref("stg_reporting__terms") }} as rt on ur.role_name = rt.grade_band
        left join {{ ref("stg_schoolmint_grow__users") }} as u on ur.user_id = u.user_id
        left join
            {{ ref("base_people__staff_roster") }} as sr
            on u.internal_id = safe_cast(sr.employee_number as string)
        where ur.role_name != 'Whetstone'
    ),
    boxes as (
        select
            observation_id,
            measurement,
            `key` as label,
            `value` as `value`,
            `value` as text_box_value,
            null as checkbox_value,
            'textbox' as `type`,
        from
            {{
                ref(
                    "stg_schoolmint_grow__observations__observation_scores__text_boxes"
                )
            }}

        union all

        select
            observation_id,
            measurement,
            label as label,
            cast(`value` as string) as `value`,
            null as text_box_value,
            cast(`value` as int) as checkbox_value,
            'checkbox' as `type`,
        from
            {{
                ref(
                    "stg_schoolmint_grow__observations__observation_scores__checkboxes"
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
            o.list_two_column_a as glows,
            o.list_two_column_b as grows,
            os.measurement as score_measurement_id,
            os.percentage as score_percentage,
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
            if(
                b.type = 'checkbox', m.name || ' - ' || b.label, m.name
            ) as measurement_label,
            null as score_type,

            coalesce(
                if(
                    sum(b.checkbox_value) over (
                        partition by o.observation_id, os.measurement
                    )
                    > 0,
                    b.checkbox_value,
                    null
                ),
                os.value_score
            ) as row_score_value,

            case
                when b.type != 'checkbox'
                then null
                when
                    sum(b.checkbox_value) over (
                        partition by o.observation_id, os.measurement
                    )
                    > 0
                then 1
                else 0
            end as checkbox_observed,
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
                else null
            end as tier,
            regexp_replace(
                regexp_replace(b.text_box_value, r'<[^>]*>', ''), r'&nbsp;', ' '
            ) as text_box,
            ROW_NUMBER() OVER (PARTITION BY o.teacher_id, o.rubric_name ORDER BY o.observed_at DESC) AS row_num,
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
        where o.observed_at >= timestamp(date({{ var("current_academic_year") }}, 7, 1))
        and o.is_published = true
    )

select s.*, o.*,
from scaffold as s
left join
    observations as o
    on cast(o.observed_at as date) between s.start_date and s.end_date
    and s.type = o.reporting_term_type
    and s.user_id = o.teacher_id
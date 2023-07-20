with
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
            o.rubric_name,
            o.created,
            o.observed_at,
            o.observer_name,
            o.observer_email,
            o.score,
            o.list_two_column_b as grows,
            o.list_two_column_a as glows,

            tsr.employee_number,
            tsr.preferred_name_lastfirst,
            tsr.business_unit_home_name,
            tsr.home_work_location_name,
            tsr.home_work_location_grade_band,
            tsr.home_work_location_powerschool_school_id,
            tsr.department_home_name,
            tsr.primary_grade_level_taught,
            tsr.job_title,
            tsr.report_to_preferred_name_lastfirst,
            tsr.worker_original_hire_date,
            tsr.assignment_status,
            {# TODO #}
            null as is_active,
            null as observee_gender,
            null as observee_ethnicity,
            regexp_extract(tsr.user_principal_name, r'(\w+)@') as teacher_username,
            regexp_extract(
                tsr.report_to_user_principal_name, r'(\w+)@'
            ) as observer_username,

            {# TODO #}
            null as observer_gender,
            null as observer_ethnicity,
            rt.academic_year,
            rt.code as reporting_term,

            row_number() over (
                partition by o.rubric_name, o.teacher_id order by o.observed_at desc
            ) as rn_observation
        from {{ ref("stg_schoolmint_grow__observations") }} as o
        inner join
            {{ ref("stg_schoolmint_grow__users") }} as ti on o.teacher_id = ti.user_id
        inner join
            {{ ref("base_people__staff_roster") }} as tsr
            on ti.internal_id = safe_cast(tsr.employee_number as string)
        inner join
            {{ ref("stg_schoolmint_grow__users") }} as oi on o.observer_id = oi.user_id
        left join
            {{ ref("base_people__staff_roster") }} as osr
            on oi.internal_id = safe_cast(osr.employee_number as string)
        inner join
            {{ ref("stg_reporting__terms") }} as rt
            on cast(o.observed_at as date) between rt.start_date and rt.end_date
            and rt.type = 'ETR'
            and rt.school_id = 0
        where
            o.observed_at >= timestamp(date({{ var("current_academic_year") }}, 7, 1))
            and o.rubric_name in (
                'Development Roadmap',
                'Shadow Session',
                'Assistant Principal PM Rubric',
                'School Leader Moments',
                'Readiness Reflection',
                'Monthly Triad Meeting Form',
                'New Leader Talent Review',
                'Extraordinary Focus Areas Ratings',
                'O3 Form',
                'O3 Form v2',
                'O3 Form v3',
                'Extraordinary Focus Areas Ratings v.1'
            )
    )

select
    os.*,

    oos.measurement as score_measurement_id,
    oos.percentage as score_percentage,
    case
        oos.value_text
        when 'Yes'
        then 3
        when 'Almost'
        then 2
        when 'No'
        then 1
        when 'On Track'
        then 3
        when 'Off Track'
        then 1
        else oos.value_score
    end as measure_value,

    m.name as measurement_name,
    m.scale_min as measurement_scale_min,
    m.scale_max as measurement_scale_max,

    if(b.type = 'checkbox', m.name || ' - ' || b.label, m.name) as measurement_label,

    case
        when os.rubric_name = 'School Leader Moments' and m.name like '%- type'
        then
            case
                oos.value_score
                when 1
                then 'Observed'
                when 2
                then 'Co-Led/Planned'
                when 3
                then 'Led'
            end
        when b.type is not null
        then b.value
        else oos.value_text
    end as score_value_text,

    max(
        case
            when os.rubric_name = 'School Leader Moments' and m.name like '%- type'
            then
                case
                    oos.value_score
                    when 1
                    then 'Observed'
                    when 2
                    then 'Co-Led/Planned'
                    when 3
                    then 'Led'
                end
        end
    ) over (partition by os.observation_id, regexp_extract(m.name, r'(\w+)- type'))
    as score_type,

    coalesce(
        if(
            sum(b.checkbox_value) over (partition by os.observation_id, oos.measurement)
            > 0,
            b.checkbox_value,
            null
        ),
        oos.value_score
    ) as score_value,

    case
        when b.type != 'checkbox'
        then null
        when
            sum(b.checkbox_value) over (partition by os.observation_id, oos.measurement)
            > 0
        then 1
        else 0
    end as checkbox_observed,
from observations as os
left join
    {{ ref("stg_schoolmint_grow__observations__observation_scores") }} as oos
    on os.observation_id = oos.observation_id
left join
    {{ ref("stg_schoolmint_grow__measurements") }} as m
    on oos.measurement = m.measurement_id
left join
    boxes as b
    on oos.observation_id = b.observation_id
    and oos.measurement = b.measurement

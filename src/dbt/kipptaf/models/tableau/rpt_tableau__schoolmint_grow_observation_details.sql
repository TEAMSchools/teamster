{{ config(enabled=False) }}
with
    boxes as (
        select
            tb.observation_id,
            tb.score_measurement_id,
            tb.text_box_label as label,
            tb.text_box_text as `value`,
            tb.text_box_text,
            null as checkbox_value,
            'textbox' as `type`,
        from whetstone.observations_scores_text_boxes_static as tb

        union all

        select
            cc.observation_id,
            cc.score_measurement_id,
            cc.checkbox_label as label,
            cast(cc.checkbox_value as string) as `value`,
            null as text_box_text,
            cast(cc.checkbox_value as numeric) as checkbox_value,
            'checkbox' as `type`,
        from whetstone.observations_scores_checkboxes_static as cc
    ),

    observation_scaffold as (
        select
            sr.df_employee_number,
            sr.preferred_name,
            sr.primary_site,
            sr.primary_on_site_department as dayforce_department,
            sr.grades_taught as dayforce_grade_team,
            sr.primary_job as dayforce_role,
            sr.legal_entity_name,
            sr.is_active,
            sr.primary_site_schoolid,
            sr.manager_name,
            sr.original_hire_date,
            sr.primary_ethnicity as observee_ethnicity,
            sr.gender as observee_gender,
            sr.status,
            sr.primary_site_school_level,
            left(
                sr.userprincipalname, charindex('@', sr.userprincipalname) - 1
            ) as staff_username,
            left(
                sr.manager_userprincipalname,
                charindex('@', sr.manager_userprincipalname) - 1
            ) as manager_username,

            osr.gender as observer_gender,
            osr.primary_ethnicity as observer_ethnicity,

            wo.observation_id,
            wo.observed_at,
            wo.created,
            wo.observer_name,
            wo.observer_email,
            wo.rubric_name,
            wo.list_two_column_a as glows,
            wo.list_two_column_b as grows,
            wo.score,

            rt.academic_year,
            rt.time_per_name as reporting_term,

            row_number() over (
                partition by sr.df_employee_number, wo.rubric_name
                order by wo.observed_at desc
            ) as rn_observation
        from people.staff_crosswalk_static as sr
        inner join
            whetstone.observations_clean as wo
            on sr.df_employee_number = wo.teacher_internal_id
            and wo.rubric_name in (
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
        left join
            people.staff_crosswalk_static as osr
            on wo.observer_internal_id = osr.df_employee_number
        inner join
            reporting.reporting_terms as rt
            on wo.observed_at between rt.start_date and rt.end_date
            and rt.identifier = 'ETR'
            and rt.schoolid = 0
            and rt._fivetran_deleted = 0
        where
            ifnull(sr.termination_date, current_timestamp)
            >= date({{ var("current_academic_year") }}, 7, 1)
    )
select
    os.*,

    wos.score_measurement_id,
    wos.score_percentage,
    case
        when wos.score_value_text = 'Yes'
        then 3
        when wos.score_value_text = 'Almost'
        then 2
        when wos.score_value_text = 'No'
        then 1
        when wos.score_value_text = 'On Track'
        then 3
        when wos.score_value_text = 'Off Track'
        then 1
        else wos.score_value
    end as measure_value,

    wm.name as measurement_name,
    wm.scale_min as measurement_scale_min,
    wm.scale_max as measurement_scale_max,

    max(
        case
            when os.rubric_name != 'School Leader Moments'
            then null
            when wm.name not like '%- type'
            then null
            when wos.score_value = 1
            then 'Observed'
            when wos.score_value = 2
            then 'Co-Led/Planned'
            when wos.score_value = 3
            then 'Led'
        end
    ) over (
        partition by os.observation_id, ltrim(rtrim(replace(wm.name, '- type', '')))
    ) as score_type,
    case
        when
            os.rubric_name = 'School Leader Moments'
            and wm.name like '%- type'
            and wos.score_value = 1
        then 'Observed'
        when
            os.rubric_name = 'School Leader Moments'
            and wm.name like '%- type'
            and wos.score_value = 2
        then 'Co-Led/Planned'
        when
            os.rubric_name = 'School Leader Moments'
            and wm.name like '%- type'
            and wos.score_value = 3
        then 'Led'
        when b.type is not null
        then b.value
        else wos.score_value_text
    end as score_value_text,
    case
        when b.type = 'checkbox' then wm.name + ' - ' + b.label else wm.name
    end as measurement_label,
    coalesce(
        case
            when
                sum(b.checkbox_value) over (
                    partition by os.observation_id, wos.score_measurement_id
                )
                > 0
            then b.checkbox_value
        end,
        wos.score_value
    ) as score_value,
    case
        when b.type != 'checkbox'
        then null
        when
            sum(b.checkbox_value) over (
                partition by os.observation_id, b.score_measurement_id
            )
            > 0
        then 1
        else 0
    end as checkbox_observed
from observation_scaffold as os
left join
    whetstone.observations_scores_static as wos
    on os.observation_id = wos.observation_id
left join whetstone.measurements as wm on wos.score_measurement_id = wm._id
left join
    boxes as b
    on os.observation_id = b.observation_id
    and wos.score_measurement_id = b.score_measurement_id

select
    o.observation_id,
    o.teacher_id,
    o.rubric_name as form_long_name,
    o.rubric_id,
    o.score as overall_score,
    o.observed_at_date_local as observed_at,
    o.list_two_column_a_str as glows,
    o.list_two_column_b_str as grows,
    o.observer_email,
    o.last_modified,
    o.observation_type,

    u.internal_id_int as employee_number,

    os.measurement as score_measurement_id,
    os.value_score as row_score_value,
    /* going away with new lockbox procedure ohos.last_modified_date_lead */
    
    m.name as measurement_name,

    mg.name as measurement_type,
    mg.abbreviation as measurement_shortname,

    b.value_clean as text_box,

    srh.employee_number as observer_employee_number,
from {{ ref("stg_schoolmint_grow__observations") }} as o
inner join {{ ref("stg_schoolmint_grow__users") }} as u on o.teacher_id = u.user_id
left join
    {{ ref("stg_schoolmint_grow__observations__observation_scores") }} as os
    on o.observation_id = os.observation_id
left join
    {{ ref("stg_schoolmint_grow__measurements") }} as m
    on os.measurement = m.measurement_id
left join
    {{
        source(
            "schoolmint_grow", "src_schoolmint_grow__generic_tags_measurementgroups"
        )
    }} as mg on m.measurement_id = mg._id
left join
    {{ ref("stg_schoolmint_grow__observations__observation_scores__text_boxes") }} as b
    on os.observation_id = b.observation_id
    and os.measurement = b.measurement

left join
    {{ ref("base_people__staff_roster_history") }} as srh
    on o.observer_email = srh.google_email
    and o.observed_at
    between srh.work_assignment_start_date and srh.work_assignment_end_date
where
    o.is_published


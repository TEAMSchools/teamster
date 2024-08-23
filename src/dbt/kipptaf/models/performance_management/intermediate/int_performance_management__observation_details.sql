select
    o.observation_id,
    o.rubric_name,
    o.observation_score,
    o.glows,
    o.grows,
    o.locked,
    o.observed_at_timestamp,
    o.observed_at,
    o.academic_year,
    o.observation_type,
    o.observation_type_abbreviation,
    o.term_code,
    o.term_name,
    o.employee_number,
    o.observer_employee_number,
    o.eval_date,
    o.overall_tier,
    o.observation_notes,

    null as etr_score,
    null as etr_tier,
    null as so_score,
    null as so_tier,

    os.value_score as row_score,

    m.name as measurement_name,

    mg.measurement_group_name as strand_name,

    /* os.value_text is dropdown selections, text box values are comments for individual */
    os.value_text as measurement_dropdown_selection,

    tb.value_clean as measurement_comments,
from {{ ref("int_performance_management__observations") }} as o
left join
    {{ ref("stg_schoolmint_grow__observations__observation_scores") }} as os
    on o.observation_id = os.observation_id
left join
    {{ ref("stg_schoolmint_grow__measurements") }} as m
    on os.measurement = m.measurement_id
left join
    {{ ref("stg_schoolmint_grow__rubrics__measurement_groups__measurements") }} as mgm
    on o.rubric_id = mgm.rubric_id
    and m.measurement_id = mgm.measurement_id
left join
    {{ ref("stg_schoolmint_grow__rubrics__measurement_groups") }} as mg
    on mgm.rubric_id = mg.rubric_id
    and mgm.measurement_group_id = mg.measurement_group_id
left join
    {{ ref("stg_schoolmint_grow__observations__observation_scores__text_boxes") }} as tb
    on os.observation_id = tb.observation_id
    and os.measurement = tb.measurement

union all

select
    observation_id,
    rubric_name,
    score as observation_score,
    glows,
    grows,
    locked,
    observed_at as observed_at_timestamp,
    observed_at_date_local as observed_at,
    academic_year,
    observation_type,
    observation_type_abbreviation,
    term_code,
    term_name,
    employee_number,
    observer_employee_number,
    eval_date,
    overall_tier,
    null as observation_notes,
    etr_score,
    etr_tier,
    so_score,
    so_tier,
    value_score as row_score,
    measurement_name,
    measurement_group_name as strand_name,
    null as dropdown_selection,
    text_box as measurement_comments,
from {{ ref("stg_performance_management__observation_details_archive") }}

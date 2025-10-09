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

    os.value_score as row_score,
    os.value_text as measurement_dropdown_selection,
    os.text_box_value_clean as measurement_comments,

    m.name as measurement_name,

    mgm.measurement_group_name as strand_name,

    null as etr_score,
    null as etr_tier,
    null as so_score,
    null as so_tier,
from {{ ref("int_performance_management__observations") }} as o
left join
    {{ ref("int_schoolmint_grow__observations__observation_scores") }} as os
    on o.observation_id = os.observation_id
left join
    {{ ref("stg_schoolmint_grow__measurements") }} as m
    on os.measurement = m.measurement_id
left join
    {{ ref("stg_schoolmint_grow__rubrics__measurement_groups__measurements") }} as mgm
    on o.rubric_id = mgm.rubric_id
    and m.measurement_id = mgm.measurement_id

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

    value_score as row_score,

    null as measurement_dropdown_selection,

    text_box as measurement_comments,
    measurement_name,
    measurement_group_name as strand_name,
    etr_score,
    etr_tier,
    so_score,
    so_tier,
from
    {{
        source(
            "performance_management",
            "stg_performance_management__observation_details_archive",
        )
    }}

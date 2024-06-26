select
    o.observation_id,
    o.rubric_name,
    o.observation_score,
    o.strand_score,
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
    o.etr_score,
    o.etr_tier,
    o.so_score,
    o.so_tier,

    coalesce(os.value_score, arc.value_score) as row_score,

    coalesce(m.name, arc.measurement_name) as measurement_name,

    coalesce(mg.measurement_group_name, arc.measurement_group_name) as strand_name,

    coalesce(tb.value_clean, arc.text_box) as text_box,
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
    on o.rubric_id = mgm.rubric_id
left join
    {{ ref("stg_schoolmint_grow__observations__observation_scores__text_boxes") }} as tb
    on os.observation_id = tb.observation_id
    and os.measurement = tb.measurement
left join
    {{ ref("stg_performance_management__observation_details_archive") }} as arc
    on o.observation_id = arc.observation_id
where o.academic_year = {{ var("current_academic_year") }} and o.is_published

/* current academic year */

select
    o.observation_id,
    o.rubric_name,
    o.score as observation_score,
    o.score_averaged_by_strand as strand_score,
    o.glows,
    o.grows,
    o.locked,
    o.observed_at_date_local as observed_at,
    o.academic_year,
    gt.name as observation_type,
    gt.abbreviation as observation_type_abbreviation,
    t.code,
    t.name,
    os.value_score as row_score,
    m.name as measurement_name,
    mgm.strand_name,
    tb.value_clean as text_box,
    srh.employee_number,
    srho.employee_number as observer_employee_number,
from {{ ref("stg_schoolmint_grow__observations") }} as o
left join
    {{ ref("stg_schoolmint_grow__generic_tags") }} as gt
    on o.observation_type = gt.tag_id
left join
    {{ ref("stg_reporting__terms") }} as t
    on gt.abbreviation = t.type
    and o.observed_at_date_local between t.start_date and t.end_date
left join
    {{ ref("stg_schoolmint_grow__observations__observation_scores") }} as os
    on o.observation_id = os.observation_id
left join
    {{ ref("stg_schoolmint_grow__measurements") }} as m
    on os.measurement = m.measurement_id
left join
    {{ ref("stg_schoolmint_grow__rubrics__measurement_groups__measurements") }} as mgm
    on m.measurement_id = mgm.measurement_id
    and o.rubric_id = mgm.rubric_id
left join
    {{ ref("stg_schoolmint_grow__observations__observation_scores__text_boxes") }} as tb
    on os.observation_id = tb.observation_id
    and os.measurement = tb.measurement
/* join on google email and date for employee_number*/
left join
    {{ ref("base_people__staff_roster_history") }} as srh
    on o.teacher_email = srh.google_email
    and o.observed_at
    between srh.work_assignment_start_date and srh.work_assignment_end_date
/* join on google email and date for observer_employee_number*/
left join
    {{ ref("base_people__staff_roster_history") }} as srho
    on o.observer_email = srh.google_email
    and o.observed_at
    between srho.work_assignment_start_date and srho.work_assignment_end_date
where
    o.academic_year = {{ var("current_academic_year") }}
    and o.is_published
    and o.archived_at is null

-- union all 

-- /* past academic years */

-- select
--     o.observation_id,
--     o.rubric_name,
--     o.score as observation_score,
--     o.score_averaged_by_strand as strand_score,
--     o.glows,
--     o.grows,
--     o.locked,
--     o.observed_at_date_local as observed_at,
--     o.academic_year,
--     gt.name as observation_type,
--     gt.abbreviation as observation_type_abbreviation,
--     os.value_score as row_score,
--     m.name as measurement_name,
--     mgm.strand_name,
--     tb.value_clean as text_box,
--     srh.employee_number,
--     srho.employee_number as observer_employee_number,

--     from {{ ref('stg_performance_management__observation_details') }}
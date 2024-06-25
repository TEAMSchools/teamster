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
    sr.employee_number,
    sr2.employee_number as observer_employee_number,
    null as etr_score,
    null as so_score,
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
    {{ ref("base_people__staff_roster") }} as sr on o.teacher_email = sr.google_email
/* join on google email and date for observer_employee_number*/
left join
    {{ ref("base_people__staff_roster") }} as sr2 on o.observer_email = sr2.google_email
where
    o.academic_year = {{ var("current_academic_year") }}
    and o.is_published
    and o.archived_at is null

union all

-- /* past academic years (Performance Management only) */
select
    observation_id,
    form_long_name as rubric_name,
    overall_score as observation_score,
    case
        when score_measurement_type = 'etr'
        then etr_score
        when score_measurement_type = 's&o'
        then so_score
    end as strand_score,
    glows,
    grows,
    true as locked,
    date(observed_at) as observed_at,
    academic_year,
    'Teacher Performance Management' as observation_type,
    'PM' as observation_type_abbreviation,
    form_term as code,
    'Coaching Tool: Coach ETR and Reflection' as `name`,
    row_score_value as row_score,
    measurement_name,
    case
        when score_measurement_type = 'etr'
        then 'Excellent Teaching Rubric'
        when score_measurement_type = 's&o'
        then 'Self & Others: Manager Feedback'
        else 'Comments'
    end as strand_name,
    text_box,
    employee_number,
    observer_employee_number,
    etr_score,
    so_score,
from {{ ref("stg_performance_management__observation_details") }}

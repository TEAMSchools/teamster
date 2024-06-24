/* current academic year observations*/
select
    o.observation_id,
    o.rubric_name,
    o.score as observation_score,
    o.score_averaged_by_strand as strand_score,
    o.list_two_column_a_str as glows,
    o.list_two_column_b_str as grows,
    o.observed_at_date_local as observed_at,
    o.academic_year,
    o.locked,
    ot.name as observation_type,
    ot.abbreviation as observation_type_abbreviation,
    os.value_score as row_score,
    m.name as measurement_name,
    mgm.strand_name,
    mgm.strand_description,
    b.value_clean as text_box,
    coalesce(u.internal_id_int, srh.employee_number) as employee_number,
    srh.report_to_employee_number as observer_employee_number,

    t.code,

from {{ ref("stg_schoolmint_grow__observations") }} as o
left join {{ ref('stg_reporting__terms') }} as t
on o.observation_type = t.type 
and o.observed_at between t.start_date and t.end_date
left join
    {{
        source(
            "schoolmint_grow",
            "src_schoolmint_grow__generic_tags_observationtypes",
        )
    }} as ot on o.observation_type = ot._id
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
inner join {{ ref("stg_schoolmint_grow__users") }} as u on o.teacher_id = u.user_id
/* join to get info on non-active SMG users */
left join
    {{ ref("base_people__staff_roster_history") }} as srh
    on o.teacher_email = srh.google_email
    and o.observed_at
    between srh.work_assignment_start_date and srh.work_assignment_end_date
left join
    {{ ref("stg_schoolmint_grow__observations__observation_scores__text_boxes") }} as b
    on os.observation_id = b.observation_id
    and os.measurement = b.measurement
where
    o.is_published
    and o.archived_at is null
    and o.academic_year = {{ var("current_academic_year") }}

union all

/* Teacher Performance Management Staging Table - Couchdrop */
select
    od.observation_id,
    od.rubric_name,

    od.observation_score,
    case
        when od.strand_name = 'etr'
        then od.etr_score
        when od.strand_name = 's&o'
        then od.so_score
    end as strand_score,
    null as glows,
    null as grows,
    od.observed_at,
    od.academic_year,
    true as locked,
    'Teacher Performance Management' as observation_type,
    'PM' as observation_type_abbreviation,
    od.row_score,
    od.measurement_name,
    case
        when od.strand_name = 'etr'
        then 'Excellent Teaching Rubric'
        when od.strand_name = 's&o'
        then 'Self & Others: Manager Feedback'
    end as strand_name,
    null as strand_description,
    od.text_box,
    od.employee_number,
    od.observer_employee_number,
    od.code,

from {{ ref("stg_performance_management__observation_details") }} as od

union all

/* Teacher Performance Management 2022 and prior */
select
    soa.observation_id,
    'Coaching Tool: Coach ETR and Reflection' as rubric_name,

    soa.overall_score as observation_score,
    case
        when sda.score_type = 'ETR'
        then soa.etr_score
        when sda.score_type = 'S&O'
        then soa.so_score
    end as strand_score,
    null as glows,
    null as grows,
    sda.observed_at,
    sda.academic_year,
    true as locked,
    'Teacher Performance Management' as observation_type,
    'PM' as observation_type_abbreviation,
    sda.row_score,
    sda.measurement_name,
    case
        when sda.score_type = 'ETR'
        then 'Excellent Teaching Rubric'
        when sda.score_type = 'S&O'
        then 'Self & Others: Manager Feedback'
    end as strand_name,  
    null as strand_description,
    null as text_box,
    soa.employee_number,
    sda.observer_employee_number,
        soa.code,

from {{ ref("stg_performance_management__scores_overall_archive") }} as soa
inner join
    {{ ref("stg_performance_management__scores_detail_archive") }} as sda
    on soa.employee_number = sda.employee_number
    and soa.academic_year = sda.academic_year
    and soa.code = sda.code
left join
    {{ ref("base_people__staff_roster_history") }} as sr
    on sda.observer_employee_number = sr.employee_number
where sda.row_score is not null

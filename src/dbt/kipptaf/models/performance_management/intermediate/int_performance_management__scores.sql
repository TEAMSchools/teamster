/* current academic year observations*/

select
    o.observation_id,
    o.rubric_name,
    o.score as observation_score,
    o.score_averaged_by_strand as strand_score,
    o.observed_at_date_local as observed_at,
    o.list_two_column_a_str as glows,
    o.list_two_column_b_str as grows,
    o.last_modified,
    o.locked,
    o.academic_year,

    case
        when ot.name is not null
        then ot.name
        /* for prior years*/
        when o.rubric_name like '%ETR%'
        then 'Teacher Performance Management'
        when o.rubric_name like '%O3%'
        then 'O3'
        when o.rubric_name like '%Walkthrough%'
        then 'Walkthrough'
    end as observation_type,
    case
        when ot.abbreviation is not null
        then ot.abbreviation
        /* for prior years*/
        when o.rubric_name like '%ETR%'
        then 'PM'
        when o.rubric_name like '%O3%'
        then 'O3'
        when o.rubric_name like '%Walkthrough%'
        then 'WT'
    end as observation_type_abbreviation,

    os.value_score as row_score,

    m.name as measurement_name,

    mgm.strand_name,
    mgm.strand_description,

    b.value_clean as text_box,
    coalesce(u.internal_id_int, srh.employee_number) as employee_number,
    srh.report_to_employee_number as observer_employee_number,

from {{ ref("stg_schoolmint_grow__observations") }} as o
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
inner join {{ ref("stg_schoolmint_grow__users") }} as u on o.teacher_id = u.user_id
/* join to get info on non-active SMG users*/
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

/* 2024+ All Observation Types */
select
    o.observation_id,
    o.rubric_id,
    o.rubric_name,
    o.score as observation_score,
    o.score_averaged_by_strand as strand_score,
    o.glows,
    o.grows,
    o.locked,
    o.observed_at as observed_at_timestamp,
    o.observed_at_date_local as observed_at,
    o.academic_year,
    o.is_published,
    o.teacher_internal_id as employee_number,
    o.observer_internal_id as observer_employee_number,
    o.observation_type_name as observation_type,
    o.observation_type_abbreviation,

    t.code as term_code,
    t.name as term_name,

    case
        when o.score >= 3.495
        then 4
        when o.score >= 2.745
        then 3
        when o.score >= 1.745
        then 2
        when o.score < 1.75
        then 1
    end as overall_tier,

    case
        when t.code = 'PM1'
        then date(o.academic_year, 10, 1)
        when t.code = 'PM2'
        then date(o.academic_year + 1, 1, 1)
        when t.code = 'PM3'
        then date(o.academic_year + 1, 3, 1)
    end as eval_date,
from {{ ref("int_schoolmint_grow__observations") }} as o
inner join {{ ref("stg_people__location_crosswalk") }} as lc on o.school_name = lc.name
left join
    {{ ref("stg_reporting__terms") }} as t
    on o.observation_type_abbreviation = t.type
    and o.observed_at_date_local between t.start_date and t.end_date
    and lc.region = t.region
/* data prior to 2024 in snapshot */
where o.is_published and o.academic_year >= 2024

union all

/* 2023 Walkthroughs */
select
    o.observation_id,
    o.rubric_id,
    o.rubric_name,
    o.score as observation_score,
    o.score_averaged_by_strand as strand_score,
    o.glows,
    o.grows,
    o.locked,
    o.observed_at as observed_at_timestamp,
    o.observed_at_date_local as observed_at,
    o.academic_year,
    o.is_published,
    o.teacher_internal_id as employee_number,
    o.observer_internal_id as observer_employee_number,

    'Walkthrough' as observation_type,
    'WT' as observation_type_abbreviation,

    t.code as term_code,
    t.name as term_name,

    null as overall_tier,
    null as eval_date,
from {{ ref("int_schoolmint_grow__observations") }} as o
left join
    {{ ref("stg_reporting__terms") }} as t
    on o.observed_at_date_local between t.start_date and t.end_date
    and t.type = 'WT'
where
    o.academic_year = 2023
    and o.is_published
    and (
        contains_substr(o.rubric_name, 'Walkthrough')
        or contains_substr(o.rubric_name, 'Strong Start')
    )

/* current academic year */
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

    gt.name as observation_type,
    gt.abbreviation as observation_type_abbreviation,

    t.code as term_code,
    t.name as term_name,

    sr.employee_number,

    sr2.employee_number as observer_employee_number,

    null as etr_score,
    null as etr_tier,
    null as so_score,
    null as so_tier,

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
from {{ ref("stg_schoolmint_grow__observations") }} as o
left join
    {{ ref("stg_schoolmint_grow__generic_tags") }} as gt
    on o.observation_type = gt.tag_id
left join
    {{ ref("stg_reporting__terms") }} as t
    on gt.abbreviation = t.type
    and o.observed_at_date_local between t.start_date and t.end_date
/* join on google email and date for employee_number*/
left join
    {{ ref("base_people__staff_roster") }} as sr on o.teacher_email = sr.google_email
/* join on google email and date for observer_employee_number*/
left join
    {{ ref("base_people__staff_roster") }} as sr2 on o.observer_email = sr2.google_email
where o.academic_year = {{ var("current_academic_year") }} and o.is_published

union all

/* past academic years (Performance Management only) */
select
    observation_id,
    null as rubric_id,
    rubric_name,
    score as observation_score,
    null as strand_score,
    glows,
    grows,
    locked,
    observed_at as observed_at_timestamp,
    observed_at_date_local as observed_at,
    academic_year,
    null as is_published,
    observation_type,
    observation_type_abbreviation,
    term_code,
    term_name,
    employee_number,
    observer_employee_number,
    etr_score,
    etr_tier,
    so_score,
    so_tier,
    overall_tier,
    eval_date,
from {{ ref("int_performance_management__observations_archive") }}

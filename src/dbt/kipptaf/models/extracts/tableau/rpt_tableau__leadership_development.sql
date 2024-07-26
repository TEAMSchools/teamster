with
    round_completion as (
        select
            employee_number,
            academic_year,
            if(count(notes_boy) > 4, 1, 0) as boy_complete,
            if(count(rating_moy) > 4, 1, 0) as moy_self_complete,
            if(count(manager_rating_moy) > 4, 1, 0) as moy_manager_complete,
            if(count(rating_eoy) > 4, 1, 0) as eoy_self_complete,
            if(count(manager_rating_eoy) > 4, 1, 0) as eoy_manager_complete,
        from {{ ref("stg_leadership_development_output") }}
        group by employee_number, academic_year
    ),

    metrics_lookup as (
        select distinct
            m.metric_id, m.region, m.bucket, m.type, m.description, m.fiscal_year,
        from
            {{ ref("stg_performance_management__leadership_development_metrics") }} as m
    )

select

    o.employee_number,
    o.academic_year,
    o.metric_id,
    o.assignment_id,
    o.notes_boy,
    o.rating_moy,
    o.rating_eoy,
    o.notes_moy,
    o.notes_eoy,
    o.manager_rating_moy,
    o.manager_rating_eoy,
    o.manager_notes_moy,
    o.manager_notes_eoy,

    m.metric_id,
    m.region,
    m.bucket,
    m.type,
    m.description,
    m.fiscal_year,

    c.boy_complete,
    c.moy_self_complete,
    c.moy_manager_complete,
    c.eoy_self_complete,
    c.eoy_manager_complete,

from {{ ref("stg_leadership_development_output") }} as o
left join metrics_lookup as m on o.metric_id = m.metric_id
left join
    round_completion as c
    on o.employee_number = c.employee_number
    and o.academic_year = c.academic_year
where active_assignment

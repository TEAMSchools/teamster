with
    pivot as (
        select
            o.employee_number,
            o.academic_year,
            o.metric_id,
            o.assignment_id,
            o.active_assignment,
            column_name,
            column_value,
            case
                when contains_substr(column_name, 'boy')
                then 'BOY'
                when contains_substr(column_name, 'moy')
                then 'MOY'
                when contains_substr(column_name, 'eoy')
                then 'EOY'
            end as term,
        from
            {{ ref("stg_leadership_development__output") }} as o,
            unnest(
                [
                    struct('notes_boy' as column_name, o.notes_boy as column_value),
                    struct('rating_moy' as column_name, o.rating_moy as column_value),
                    struct('rating_eoy' as column_name, o.rating_eoy as column_value),
                    struct('notes_moy' as column_name, o.notes_moy as column_value),
                    struct('notes_eoy' as column_name, o.notes_eoy as column_value),
                    struct(
                        'manager_rating_moy' as column_name,
                        o.manager_rating_moy as column_value
                    ),
                    struct(
                        'manager_rating_eoy' as column_name,
                        o.manager_rating_eoy as column_value
                    ),
                    struct(
                        'manager_notes_moy' as column_name,
                        o.manager_notes_moy as column_value
                    ),
                    struct(
                        'manager_notes_eoy' as column_name,
                        o.manager_notes_eoy as column_value
                    )
                ]
            ) as pivot
    ),

    completion as (
        select
            employee_number,
            academic_year,
            column_name,
            count(column_value) as count_done,
            case
                when column_name = 'notes_boy' and count(column_value) >= 2
                then 1
                when count(column_value) >= 4
                then 1
                else 0
            end as round_completion,
        from pivot
        group by employee_number, academic_year, column_name
    ),
    
    metrics_lookup as (
        select distinct
            m.metric_id, m.region, m.bucket, m.type, m.description, m.fiscal_year,
        from
            {{ ref("stg_performance_management__leadership_development_metrics") }} as m
    )

select
    p.employee_number,
    p.academic_year,
    p.assignment_id,
    p.active_assignment,
    p.column_name,
    p.column_value,

    a.active_title,

    m.metric_id,
    m.region,
    m.bucket,
    m.type,
    m.description,
    m.fiscal_year,

    c.round_completion,

    r.preferred_name_lastfirst,
    r.sam_account_name,
    r.job_title,
    r.business_unit_home_name as entity,
    r.home_work_location_name as `location`,
    r.department_home_name as department,
    r.report_to_preferred_name_lastfirst as manager,
    r.report_to_sam_account_name,
    r.assignment_status,

from pivot as p
left join
    {{ ref("stg_leadership_development__active_users") }} as a
    on p.employee_number = a.employee_number
left join
    completion as c
    on p.employee_number = c.employee_number
    and p.academic_year = c.academic_year
    and p.column_name = c.column_name
left join metrics_lookup as m on p.metric_id = m.metric_id
left join
    {{ ref("base_people__staff_roster") }} as r on p.employee_number = r.employee_number

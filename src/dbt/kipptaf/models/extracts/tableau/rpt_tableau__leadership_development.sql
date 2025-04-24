with
    pivot as (
        select
            o.employee_number,
            o.academic_year,
            o.metric_id,
            o.assignment_id,
            o.active_assignment,
            o.notes_boy,
            column_name,
            column_value,
            case
                when column_name like '%boy%'
                then 'BOY'
                when column_name like '%moy%'
                then 'MOY'
                when column_name like '%eoy%'
                then 'EOY'
            end as term
        from
            `teamster-332318`.`kipptaf_google_appsheet`.`stg_leadership_development__output`
            as o
        cross join
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

    self_completion as (
        select
            employee_number,
            academic_year,
            term,
            count(column_value) as response_rows_self,
        from pivot
        where column_name in ('notes_boy', 'rating_moy', 'rating_eoy')
        group by employee_number, academic_year, term

    ),

    manager_completion as (
        select
            employee_number,
            academic_year,
            term,
            count(column_value) as response_rows_manager,
        from pivot
        where column_name in ('manager_rating_moy', 'manager_rating_eoy')
        group by employee_number, academic_year, term

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
    p.term,
    p.assignment_id,
    p.active_assignment,
    p.column_name,
    p.column_value,

    a.active_title,

    m.metric_id,
    m.region,
    m.bucket,
    m.type,
    m.fiscal_year,

    r.formatted_name as preferred_name_lastfirst,
    r.sam_account_name,
    r.job_title,
    r.home_business_unit_name as entity,
    r.home_work_location_name as `location`,
    r.home_department_name as department,
    r.reports_to_formatted_name as manager,
    r.reports_to_sam_account_name as report_to_sam_account_name,
    r.assignment_status,

    case when m.bucket = 'Goals' then p.notes_boy else m.description end as description,

    case
        when c.term = 'BOY' and c.response_rows_self >= 2
        then 1
        when c.term = 'MOY' and c.response_rows_self >= 3
        then 1
        when c.term = 'EOY' and c.response_rows_self >= 3
        then 1
        else 0
    end as round_completion_self,
    case
        when c.term = 'BOY' and c.response_rows_self >= 2
        then 1
        when mc.term = 'MOY' and mc.response_rows_manager >= 10
        then 1
        when mc.term = 'EOY' and mc.response_rows_manager >= 10
        then 1
        else 0
    end as round_completion_manager,
from pivot as p
left join
    {{ ref("stg_leadership_development__active_users") }} as a
    on p.employee_number = a.employee_number
left join
    self_completion as c
    on p.employee_number = c.employee_number
    and p.academic_year = c.academic_year
    and p.term = c.term
left join
    manager_completion as mc
    on p.employee_number = mc.employee_number
    and p.academic_year = mc.academic_year
    and p.term = mc.term
left join metrics_lookup as m on p.metric_id = m.metric_id
left join
    {{ ref("int_people__staff_roster") }} as r on p.employee_number = r.employee_number

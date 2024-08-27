with
    date_range as (
        select date_trunc(date('2022-07-01') + interval n month, month) as month_start
        from
            unnest(
                generate_array(
                    0, (({{ var("current_academic_year") + 1 }} - 2022) * 12)
                )
            ) as n
    ),

    months as (
        select
            {{
                teamster_utils.date_to_fiscal_year(
                    date_field="month_start", start_month=7, year_source="start"
                )
            }} as academic_year,
            extract(month from month_start) as month,
            format_date('%B', month_start) as month_name,
            date(month_start) as start_date,
            last_day(month_start) as end_date
        from date_range
    ),

    suspension_type as (
        select penalty_name, 'ISS' as suspension_type,
        from
            unnest(
                [
                    'In School Suspension',
                    'KM: In-School Suspension',
                    'KNJ: In-School Suspension'
                ]
            ) as penalty_name

        union all

        select penalty_name, 'OSS' as suspension_type,
        from
            unnest(
                [
                    'Out of School Suspension',
                    'KM: Out-of-School Suspension',
                    'KNJ: Out-of-School Suspension'
                ]
            ) as penalty_name
    ),

    suspension_dates as (
        select
            i._dbt_source_relation,
            i.student_school_id as student_number,
            i.create_ts_academic_year as academic_year,

            min(p.start_date) as first_suspension_date,

            min(
                if(s.suspension_type = 'ISS', p.start_date, null)
            ) as first_suspension_date_iss,
            min(
                if(s.suspension_type = 'OSS', p.start_date, null)
            ) as first_suspension_date_oss,
        from {{ ref("stg_deanslist__incidents") }} as i
        inner join
            {{ ref("stg_deanslist__incidents__penalties") }} as p
            on i.incident_id = p.incident_id
            and {{ union_dataset_join_clause(left_alias="i", right_alias="p") }}
            and p.is_suspension
        inner join suspension_type as s on p.penalty_name = s.penalty_name
        group by i._dbt_source_relation, i.student_school_id, i.create_ts_academic_year
    ),

    susp_days as (
        select
            i.create_ts_academic_year as academic_year,
            i.student_school_id as student_number,

            s.suspension_type,

            p.incident_penalty_id,
            p.end_date,
            p.num_days,
        from {{ ref("stg_deanslist__incidents") }} as i
        inner join
            {{ ref("stg_deanslist__incidents__penalties") }} as p
            on i.incident_id = p.incident_id
            and {{ union_dataset_join_clause(left_alias="i", right_alias="p") }}
            and p.is_suspension
        inner join suspension_type as s on p.penalty_name = s.penalty_name
    )

select
    co.student_number,
    co.lastfirst,
    co.academic_year,
    co.region,
    co.school_level,
    co.school_abbreviation as school,
    co.grade_level,
    co.advisory_name as team,
    co.entrydate,
    co.exitdate,
    co.special_education_code,
    co.is_504,
    co.lep_status,
    co.gender,
    co.ethnicity,
    co.is_out_of_district,
    co.is_self_contained,

    m.start_date,
    m.end_date,
    m.month_name,

    s.first_suspension_date,
    s.first_suspension_date_iss,
    s.first_suspension_date_oss,

    if(co.spedlep like 'SPED%', 'IEP', 'No IEP') as iep_status,

    if(m.start_date >= s.first_suspension_date, 1, 0) as is_susp_running,
    if(m.start_date >= s.first_suspension_date_iss, 1, 0) as is_iss_running,
    if(m.start_date >= s.first_suspension_date_oss, 1, 0) as is_oss_running,

    sum(sd.num_days) over (
        partition by co.student_number, co.academic_year order by m.month asc
    ) as total_suspended_days_running,
    sum(if(sd.suspension_type = 'OSS', sd.num_days, null)) over (
        partition by co.student_number, co.academic_year order by m.month asc
    ) as oss_suspended_days_running,
    sum(if(sd.suspension_type = 'ISS', sd.num_days, null)) over (
        partition by co.student_number, co.academic_year order by m.month asc
    ) as iss_suspended_days_running,
    count(sd.incident_penalty_id) over (
        partition by co.student_number, co.academic_year order by m.month asc
    ) as total_suspension_incidents_running,
from {{ ref("base_powerschool__student_enrollments") }} as co
inner join
    months as m
    on co.academic_year = m.academic_year
    and (
        m.start_date between co.entrydate and co.exitdate
        or m.end_date between co.entrydate and co.exitdate
    )
-- inner join
-- unnest(
-- generate_date_array(
-- date({{ var("current_academic_year") - 1 }}, 8, 1),
-- current_date('{{ var("local_timezone") }}')
-- )
-- ) as date_day
-- on date_day between co.entrydate and date(co.academic_year + 1, 6, 30)
left join
    suspension_dates as s
    on co.student_number = s.student_number
    and co.academic_year = s.academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="s") }}
left join
    susp_days as sd
    on co.student_number = sd.student_number
    and co.academic_year = sd.academic_year
    and sd.end_date between m.start_date and m.end_date
-- and date_day = sd.end_date
where
    co.rn_year = 1
    and co.academic_year >= {{ var("current_academic_year") - 1 }}
    and co.grade_level != 99
    and co.student_number = 201020

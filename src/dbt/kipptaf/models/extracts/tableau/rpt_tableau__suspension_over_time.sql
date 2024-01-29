with
    date_range as (
        select safe_cast(date_day as date) as date_day,
        from {{ ref("utils__date_spine") }}
        where
            date_day
            between date({{ var("current_academic_year") }} - 1, 8, 1) and current_date(
                '{{ var("local_timezone") }}'
            )
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
            i.create_ts_academic_year as academic_year,
            i.student_school_id as student_number,
            min(p.start_date) as first_suspension_date,
            min(
                if(s.suspension_type = 'ISS', p.start_date, null)
            ) as first_suspension_date_iss,
            min(
                if(s.suspension_type = 'OSS', p.start_date, null)
            ) as first_suspension_date_oss,
        from {{ ref("stg_deanslist__incidents__penalties") }} as p
        inner join suspension_type as s on p.penalty_name = s.penalty_name
        left join
            {{ ref("stg_deanslist__incidents") }} as i on p.incident_id = i.incident_id
        where p.is_suspension
        group by i.create_ts_academic_year, i.student_school_id
    )
select
    co.academic_year,
    co.student_number,
    co.lastfirst,
    co.school_abbreviation as school,
    co.grade_level,
    co.advisory_name as team,
    co.entrydate,
    co.exitdate,
    co.is_504,
    co.lep_status,
    co.gender,
    co.ethnicity,
    co.is_out_of_district,
    co.is_self_contained,
    co.special_education_code,

    d.date_day,

    s.first_suspension_date,
    s.first_suspension_date_iss,
    s.first_suspension_date_oss,

    if(co.spedlep like 'SPED%', 'IEP', 'No IEP') as iep_status,
    if(d.date_day >= s.first_suspension_date, 1, 0) as is_susp_running,
    if(d.date_day >= s.first_suspension_date_iss, 1, 0) as is_iss_running,
    if(d.date_day >= s.first_suspension_date_oss, 1, 0) as is_oss_running,
from {{ ref("base_powerschool__student_enrollments") }} as co
inner join date_range as d on d.date_day >= co.entrydate
left join
    suspension_dates as s
    on co.academic_year = s.academic_year
    and co.student_number = s.student_number
where
    co.academic_year >= {{ var("current_academic_year") }} - 1
    and co.rn_year = 1
    and co.grade_level != 99

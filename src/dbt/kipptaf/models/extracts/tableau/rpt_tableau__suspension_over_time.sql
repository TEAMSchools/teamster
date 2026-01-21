with
    suspension_dates as (
        select
            _dbt_source_relation,
            student_school_id as student_number,
            create_ts_academic_year as academic_year,

            min(`start_date`) as first_suspension_date,

            min(
                if(suspension_type = 'ISS', `start_date`, null)
            ) as first_suspension_date_iss,

            min(
                if(suspension_type = 'OSS', `start_date`, null)
            ) as first_suspension_date_oss,
        from {{ ref("int_deanslist__incidents__penalties") }}
        where is_suspension
        group by _dbt_source_relation, student_school_id, create_ts_academic_year
    )

select
    co.student_number,
    co.student_name as lastfirst,
    co.academic_year,
    co.region,
    co.school_level,
    co.school,
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
    co.iep_status,

    date_day,

    s.first_suspension_date,
    s.first_suspension_date_iss,
    s.first_suspension_date_oss,

    rt.name as term,

    if(date_day = rt.end_date, true, false) as is_last_day_of_term,

    if(date_day >= s.first_suspension_date, 1, 0) as is_susp_running,
    if(date_day >= s.first_suspension_date_iss, 1, 0) as is_iss_running,
    if(date_day >= s.first_suspension_date_oss, 1, 0) as is_oss_running,

    sum(sd.num_days) over (
        partition by co.student_number, co.academic_year order by date_day asc
    ) as total_suspended_days_running,

    sum(if(sd.suspension_type = 'OSS', sd.num_days, null)) over (
        partition by co.student_number, co.academic_year order by date_day asc
    ) as oss_suspended_days_running,

    sum(if(sd.suspension_type = 'ISS', sd.num_days, null)) over (
        partition by co.student_number, co.academic_year order by date_day asc
    ) as iss_suspended_days_running,

    count(sd.incident_penalty_id) over (
        partition by co.student_number, co.academic_year order by date_day asc
    ) as total_suspension_incidents_running,
from {{ ref("int_extracts__student_enrollments") }} as co
inner join
    unnest(
        generate_date_array(
            '{{ var("current_academic_year") - 1 }}-08-01',
            current_date('{{ var("local_timezone") }}')
        )
    ) as date_day
    on date_day between co.entrydate and date(co.academic_year + 1, 6, 30)
left join
    suspension_dates as s
    on co.student_number = s.student_number
    and co.academic_year = s.academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="s") }}
left join
    {{ ref("int_deanslist__incidents__penalties") }} as sd
    on co.student_number = sd.student_school_id
    and co.academic_year = sd.create_ts_academic_year
    and date_day = sd.end_date
    and sd.is_suspension
left join
    {{ ref("stg_google_sheets__reporting__terms") }} as rt
    on date_day between rt.start_date and rt.end_date
    and co.schoolid = rt.school_id
    and co.academic_year = rt.academic_year
    and rt.type = 'RT'
where co.rn_year = 1 and co.academic_year >= {{ var("current_academic_year") - 1 }}

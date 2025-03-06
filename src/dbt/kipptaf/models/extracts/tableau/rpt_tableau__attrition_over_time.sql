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
    co.exit_code_kf as summer_transfer_code,
    co.exit_code_ts as ktaf_exit_code,
    co.special_education_code,
    co.is_504,
    co.lep_status,
    co.gender,
    co.ethnicity,
    co.is_out_of_district,
    co.is_self_contained,

    date_day,

    rt.name as term,

    if(date_day = rt.end_date, true, false) as is_last_day_of_term,

    if(co.spedlep like 'SPED%', 'IEP', 'No IEP') as iep_status,

    if(date_day between co.entrydate and co.exitdate, 1, 0) as is_enrolled_day,

    lag(co.is_enrolled_oct15, 1) over (
        partition by co.student_number, co.academic_year order by co.academic_year asc
    ) as is_enrolled_oct15_previous,
from {{ ref("base_powerschool__student_enrollments") }} as co
inner join
    unnest(
        generate_date_array(
            '{{ var("current_academic_year") - 1 }}-08-01',
            current_date('{{ var("local_timezone") }}')
        )
    ) as date_day
left join
    {{ ref("stg_reporting__terms") }} as rt
    on date_day between rt.start_date and rt.end_date
    and co.schoolid = rt.school_id
    and co.academic_year = rt.academic_year
    and rt.type = 'RT'
where
    co.rn_year = 1
    and co.academic_year >= {{ var("current_academic_year") - 1 }}
    and co.grade_level != 99

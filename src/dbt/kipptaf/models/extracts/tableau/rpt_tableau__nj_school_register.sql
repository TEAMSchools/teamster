with
    att_mem as (
        select
            studentid,
            yearid,
            _dbt_source_relation,

            sum(attendancevalue) as n_att,
            sum(membershipvalue) as n_mem,
            sum(
                if(
                    calendardate <= current_date('{{ var("local_timezone") }}'),
                    membershipvalue,
                    null
                )
            ) as n_mem_ytd,
        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }}
        where membershipvalue = 1
        group by studentid, yearid, _dbt_source_relation
    )

select
    co.student_number,
    co.student_name as lastfirst,
    co.academic_year,
    co.region,
    co.reporting_schoolid,
    co.grade_level,
    co.entrydate,
    co.ethnicity,
    co.lunch_status as lunchstatus,
    co.spedlep as iep_status,
    co.track,
    co.special_education_placement,
    co.programtypecode,
    co.school_calendar_days_total as n_days_school,
    co.school_calendar_days_remaining as n_days_remaining,

    sub.n_mem,
    sub.n_att,
    sub.n_mem_ytd,

    if(co.lep_status, 1, 0) as lep_status,
    if(co.is_self_contained, 1, 0) as is_pathways,
from {{ ref("int_extracts__student_enrollments") }} as co
inner join
    att_mem as sub
    on co.studentid = sub.studentid
    and co.yearid = sub.yearid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="sub") }}
where co.rn_year = 1 and co.region != 'Miami' and co.grade_level != 99

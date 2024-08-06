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
                    calendardate <= current_date('America/New_York'),
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
    co.lastfirst,
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

    d.days_total as n_days_school,
    d.days_remaining as n_days_remaining,

    sub.n_mem,
    sub.n_att,
    sub.n_mem_ytd,

    nj.programtypecode,

    if(co.lep_status, 1, 0) as lep_status,
    if(co.is_self_contained, 1, 0) as is_pathways,
from {{ ref("base_powerschool__student_enrollments") }} as co
left join
    {{ ref("int_powerschool__calendar_rollup") }} as d
    on co.schoolid = d.schoolid
    and co.yearid = d.yearid
    and co.track = d.track
    and {{ union_dataset_join_clause(left_alias="co", right_alias="d") }}
inner join
    att_mem as sub
    on co.studentid = sub.studentid
    and co.yearid = sub.yearid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="sub") }}
left join
    {{ ref("stg_powerschool__s_nj_stu_x") }} as nj
    on co.students_dcid = nj.studentsdcid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="nj") }}
where co.rn_year = 1 and co.region != 'Miami' and co.grade_level != 99

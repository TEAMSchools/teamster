with
    ada_group as (
        select
            att._dbt_source_relation,
            att.studentid,
            att.yearid,

            lower(fte.name) as fte_survey,

            max(att.attendancevalue) as attendancevalue,
            max(att.membershipvalue) as membershipvalue,
        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }} as att
        inner join
            {{ ref("stg_reporting__terms") }} as fte
            on att.yearid = fte.powerschool_year_id
            and att.calendardate between fte.start_date and fte.end_date
            and fte.type = 'FTE'
        where
            {{ extract_code_location("att") }} = 'kippmiami'
            and att.membershipvalue = 1
            and att.attendancevalue = 1
        group by att._dbt_source_relation, att.studentid, att.yearid, fte.name
    )

select
    _dbt_source_relation,
    studentid,
    yearid,
    if(attendancevalue_fte2 = 1.0, true, false) as is_present_fte2,
    if(membershipvalue_fte2 = 1.0, true, false) as is_enrolled_fte2,
    if(attendancevalue_fte3 = 1.0, true, false) as is_present_fte3,
    if(membershipvalue_fte3 = 1.0, true, false) as is_enrolled_fte3,
from
    ada_group pivot (
        max(attendancevalue) as attendancevalue,
        max(membershipvalue) as membershipvalue
        for fte_survey in ('fte2', 'fte3')
    )

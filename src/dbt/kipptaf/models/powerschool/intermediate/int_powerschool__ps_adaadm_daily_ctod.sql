with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool",
                        "int_powerschool__ps_adaadm_daily_ctod",
                    ),
                    source(
                        "kippcamden_powerschool",
                        "int_powerschool__ps_adaadm_daily_ctod",
                    ),
                    source(
                        "kippmiami_powerschool",
                        "int_powerschool__ps_adaadm_daily_ctod",
                    ),
                ]
            )
        }}
    )

select
    mem.*,

    t.academic_year,
    t.semester,
    t.term,

    cw.week_start_monday,
    cw.week_end_sunday,

    abs(mem.attendancevalue - 1) as is_absent,

    if(mem.att_code like 'T%', 0.67, mem.attendancevalue) as is_present_weighted,
    if(mem.att_code like 'T%', 1.0, 0.0) as is_tardy,
    if(mem.att_code like 'T%', 0.0, 1.0) as is_ontime,
    if(mem.att_code in ('OS', 'OSS', 'OSSP', 'SHI'), 1.0, 0.0) as is_oss,
    if(mem.att_code in ('S', 'ISS'), 1.0, 0.0) as is_iss,
    if(
        mem.att_code in ('OS', 'OSS', 'OSSP', 'S', 'ISS', 'SHI'), 1.0, 0.0
    ) as is_suspended,
from union_relations as mem
inner join
    {{ ref("int_powerschool__terms") }} as t
    on mem.yearid = t.yearid
    and mem.schoolid = t.schoolid
    and mem.calendardate between t.term_start_date and t.term_end_date
    and {{ union_dataset_join_clause(left_alias="mem", right_alias="t") }}
inner join
    {{ ref("int_powerschool__calendar_week") }} as cw
    on mem.yearid = cw.yearid
    and mem.schoolid = cw.schoolid
    and mem.calendardate between cw.week_start_monday and cw.week_end_sunday

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
                    source(
                        "kipppaterson_powerschool",
                        "int_powerschool__ps_adaadm_daily_ctod",
                    ),
                ]
            )
        }}
    ),

    calcs as (
        select
            mem.*,

            t.academic_year,
            t.semester,
            t.term,

            cw.week_start_monday,
            cw.week_end_sunday,
            cw.week_number_academic_year,

            regexp_extract(
                mem._dbt_source_relation, r'(kipp\w+)_'
            ) as _dbt_source_project,

            {# TODO: move calcs to powerschool package #}
            abs(mem.attendancevalue - 1) as is_absent,

            if(
                mem.att_code like 'T%', 0.67, mem.attendancevalue
            ) as is_present_weighted,
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
    ),

    running_calcs as (
        select
            *,

            sum(is_absent) over (
                partition by student_number, academic_year
                order by calendardate asc
                rows between 90 preceding and current row
            ) as n_absent_running_90,

            avg(is_absent) over (
                partition by academic_year, student_number order by calendardate asc
            ) as pct_absent_running_student_year,

            sum(membershipvalue) over (
                partition by academic_year, student_number
            ) as n_membership_student_year,

        from calcs
    )

select
    *,

    pct_absent_running_student_year * n_membership_student_year as n_absent_projected,

    case
        when _dbt_source_project = 'kippmiami' and n_absent_running_90 >= 15
        then true
        when
            _dbt_source_project in ('kippnewark', 'kippcamden', 'kipppaterson')
            and pct_absent_running_student_year * n_membership_student_year >= 50
        then true
        else false
    end as is_truant,
from running_calcs

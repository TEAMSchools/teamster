{%- set ignite_yearids = [] -%}
{%- for ay in var("ignite_academic_years") -%}
    {%- do ignite_yearids.append(ay - 1990) -%}
{%- endfor -%}

with
    daily as (
        select
            student_number,
            schoolid,
            attendancevalue,
            membershipvalue,

            yearid + 1990 as academic_year,
        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }}
        where
            yearid in ({{ ignite_yearids | join(", ") }})
            and grade_level in ({{ var("ignite_grade_levels") | join(", ") }})
            and student_number is not null
    )

select
    student_number,
    academic_year,
    schoolid,

    sum(attendancevalue) as days_present,
    sum(membershipvalue) as days_enrolled,
from daily
group by student_number, academic_year, schoolid

with
    attendance as (
        select
            mem.studentid,
            mem._dbt_source_relation,

            rt.name as term_name,

            mem.yearid + 1990 as academic_year,

            round(avg(mem.attendancevalue), 2) as ada_term_running,
            coalesce(sum(abs(mem.attendancevalue - 1)), 0) as n_absences_y1_running,
            coalesce(
                sum(
                    if(
                        ac.att_code not in ('ISS', 'OSS', 'OS', 'OSSP', 'SHI'),
                        abs(mem.attendancevalue - 1),
                        null
                    )
                ),
                0
            ) as n_absences_y1_running_non_susp,
        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }} as mem
        inner join
            {{ ref("stg_reporting__terms") }} as rt
            on mem.schoolid = rt.school_id
            and mem.yearid = rt.powerschool_year_id
            /* join to all terms after calendardate */
            and mem.calendardate <= rt.end_date
            and rt.type = 'RT'
        left join
            {{ ref("stg_powerschool__attendance") }} as att
            on mem.studentid = att.studentid
            and mem.calendardate = att.att_date
            and mem.schoolid = att.schoolid
            and att.att_mode_code = 'ATT_ModeDaily'
            and {{ union_dataset_join_clause(left_alias="mem", right_alias="att") }}
        left join
            {{ ref("stg_powerschool__attendance_code") }} as ac
            on att.attendance_codeid = ac.id
            and att.yearid = ac.yearid
            and att.schoolid = ac.schoolid
            and {{ union_dataset_join_clause(left_alias="att", right_alias="ac") }}
        where
            mem.membershipvalue = 1
            and mem.calendardate <= current_date('{{ var("local_timezone") }}')
        group by mem._dbt_source_relation, mem.yearid, mem.studentid, rt.name
    ),

    mclass as (
        select
            a.mclass_academic_year as academic_year,
            a.mclass_student_number as student_number,
            a.mclass_measure_standard_level,
            a.mclass_measure_standard_level_int,
            a.mclass_client_date,

            term_name,

            row_number() over (
                partition by a.mclass_academic_year, a.mclass_student_number, term_name
                order by a.mclass_client_date desc
            ) as rn_composite,
        from {{ ref("int_amplify__all_assessments") }} as a
        cross join unnest(['Q1', 'Q2', 'Q3', 'Q4']) as term_name
        where assessment_type = 'Benchmark' and mclass_measure_name_code = 'Composite'
    ),

    metric_union as (
        select
            'Attendance' as discipline,
            'ADA' as subject,

            studentid,
            null as student_number,
            _dbt_source_relation,
            academic_year,
            term_name,
            ada_term_running as metric,
        from attendance

        union all

        select
            'Attendance' as discipline,
            'Days Absent' as subject,

            studentid,
            null as student_number,
            _dbt_source_relation,
            academic_year,
            term_name,
            n_absences_y1_running_non_susp as metric,
        from attendance

        union all

        select
            'DIBELS' as discipline,
            'Benchmark' as subject,

            null as studentid,
            student_number,
            cast(null as string) as _dbt_source_relation,
            academic_year,
            term_name,
            mclass_measure_standard_level_int as metric,
        from mclass
        where rn_composite = 1
    )

select
    co.student_number,
    co.grade_level,
    co.academic_year,
    term_name,
    coalesce(mu1.discipline, mu2.discipline) as discipline,
    coalesce(mu1.subject, mu2.subject) as subject,
    coalesce(mu1.metric, mu2.metric) as metric,
from {{ ref("base_powerschool__student_enrollments") }} as co
cross join unnest(['Q1', 'Q2', 'Q3', 'Q4']) as term_name
left join
    metric_union as mu1
    on co.studentid = mu1.studentid
    and co.academic_year = mu1.academic_year
    and term_name = mu1.term_name
    and {{ union_dataset_join_clause(left_alias="co", right_alias="mu1") }}
left join
    metric_union as mu2
    on co.student_number = mu2.student_number
    and co.academic_year = mu2.academic_year
    and term_name = mu2.term_name
-- inner join
--     {{ ref("stg_reporting__promo_status_cutoffs") }} as c
--     on mu.discipline = c.discipline
--     and mu.subject = c.subject
--     and mu.academic_year = c.academic_year
--     and mu.term_name = c.code
--     and mu.region = c.region
--     and co.grade_level = c.grade_level
where co.rn_year = 1
and co.grade_level != 99
and co.academic_year = {{ var('current_academic_year') }}

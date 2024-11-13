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

    fg_credits as (
        select
            _dbt_source_relation,
            studentid,
            academic_year,
            schoolid,
            storecode,

            sum(potential_credit_hours) as enrolled_credit_hours,

            sum(if(y1_letter_grade_adjusted in ('F', 'F*'), 1, 0)) as n_failing,
            sum(
                if(
                    y1_letter_grade_adjusted in ('F', 'F*')
                    and credittype in ('ENG', 'MATH', 'SCI', 'SOC'),
                    1,
                    0
                )
            ) as n_failing_core,
            sum(
                if(
                    {# TODO: exclude credits if current year Y1 is stored #}
                    y1_letter_grade_adjusted not in ('F', 'F*'),
                    potential_credit_hours,
                    null
                )
            ) as projected_credits_y1_term,
        from {{ ref("base_powerschool__final_grades") }}
        group by _dbt_source_relation, studentid, academic_year, schoolid, storecode
    ),

    credits as (
        select
            fg._dbt_source_relation,
            fg.studentid,
            fg.academic_year,
            fg.storecode,
            fg.enrolled_credit_hours,
            fg.n_failing,
            fg.n_failing_core,
            fg.projected_credits_y1_term,

            coalesce(fg.projected_credits_y1_term, 0)
            + coalesce(gc.earned_credits_cum, 0) as projected_credits_cum,
        from fg_credits as fg
        left join
            {{ ref("int_powerschool__gpa_cumulative") }} as gc
            on fg.studentid = gc.studentid
            and fg.schoolid = gc.schoolid
            and {{ union_dataset_join_clause(left_alias="fg", right_alias="gc") }}
    ),

    metric_union_sid as (
        select
            'Attendance' as discipline,
            'ADA' as subject,

            studentid,
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
            _dbt_source_relation,
            academic_year,
            term_name,
            n_absences_y1_running_non_susp as metric,
        from attendance

        union all

        select
            'Credits' as discipline,
            'Failing Core' as subject,

            studentid,
            _dbt_source_relation,
            academic_year,
            storecode as term_name,
            n_failing_core as metric,
        from credits

        union all

        select
            'Credits' as discipline,
            'Projected' as subject,

            studentid,
            _dbt_source_relation,
            academic_year,
            storecode as term_name,
            projected_credits_cum as metric,
        from credits
    ),

    metric_union_sn as (
        select
            'DIBELS' as discipline,
            'Benchmark' as subject,

            student_number,
            academic_year,
            term_name,
            mclass_measure_standard_level_int as metric,
        from mclass
        where rn_composite = 1

        union all

        select
            'i-Ready' as discipline,
            i.subject,

            i.student_id as student_number,
            i.academic_year_int as academic_year,
            term_name,
            i.most_recent_overall_relative_placement_int as metric,
        from {{ ref("base_iready__diagnostic_results") }} as i
        cross join unnest(['Q1', 'Q2', 'Q3', 'Q4']) as term_name
    ),

    identifiers as (
        select
            co.student_number,
            co.academic_year,
            co.grade_level,
            co.is_self_contained,
            co.special_education_code,

            ps.discipline,
            ps.subject,
            ps.code as term_name,
            ps.cutoff,

            mu.metric,
        from {{ ref("base_powerschool__student_enrollments") }} as co
        inner join
            {{ ref("stg_reporting__promo_status_cutoffs") }} as ps
            on co.academic_year = ps.academic_year
            and co.region = ps.region
            and co.grade_level = ps.grade_level
            and ps.domain = 'Promotion'
            and ps.type = 'studentid'
        left join
            metric_union_sid as mu
            on co.studentid = mu.studentid
            and co.academic_year = mu.academic_year
            and ps.code = mu.term_name
            and ps.discipline = mu.discipline
            and ps.subject = mu.subject
            and {{ union_dataset_join_clause(left_alias="co", right_alias="mu") }}

        union all

        select
            co.student_number,
            co.academic_year,
            co.grade_level,
            co.is_self_contained,
            co.special_education_code,

            ps.discipline,
            ps.subject,
            ps.code as term_name,
            ps.cutoff,

            mu.metric,
        from {{ ref("base_powerschool__student_enrollments") }} as co
        inner join
            {{ ref("stg_reporting__promo_status_cutoffs") }} as ps
            on co.academic_year = ps.academic_year
            and co.region = ps.region
            and co.grade_level = ps.grade_level
            and ps.domain = 'Promotion'
            and ps.type = 'student_number'
        left join
            metric_union_sn as mu
            on co.student_number = mu.student_number
            and co.academic_year = mu.academic_year
            and ps.code = mu.term_name
            and ps.discipline = mu.discipline
            and ps.subject = mu.subject
    )

select
    *,
    case
        when discipline = 'Attendance' and subject = 'Days Absent' and cutoff <= metric
        then true
        when cutoff >= metric
        then true
        else false
    end as is_off_track,
from identifiers

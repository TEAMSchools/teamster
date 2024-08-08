with
    attendance as (
        select
            mem._dbt_source_relation,
            mem.studentid,
            mem.yearid,

            rt.name as term_name,

            round(avg(mem.attendancevalue), 2) as ada_term_running,
            coalesce(sum(abs(mem.attendancevalue - 1)), 0) as n_absences_y1_running,
            coalesce(
                sum(
                    case
                        when ac.att_code not in ('ISS', 'OSS', 'OS', 'OSSP', 'SHI')
                        then abs(mem.attendancevalue - 1)
                    end
                ),
                0
            ) as n_absences_y1_running_non_susp,
            case
                regexp_extract(mem._dbt_source_relation, r'(kipp\w+)_')
                when 'kippnewark'
                then 27
                when 'kippcamden'
                then 36
            end as hs_at_risk_absences,

            case
                when
                    regexp_extract(mem._dbt_source_relation, r'(kipp\w+)_')
                    = 'kippnewark'
                then 6 * safe_cast(right(rt.name, 1) as int)
                when
                    regexp_extract(mem._dbt_source_relation, r'(kipp\w+)_')
                    = 'kippcamden'
                then 9 * safe_cast(right(rt.name, 1) as int)
            end as hs_off_track_absences,
        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }} as mem
        inner join
            {{ ref("stg_reporting__terms") }} as rt
            on mem.schoolid = rt.school_id
            and mem.yearid = rt.powerschool_year_id
            and mem.calendardate <= rt.end_date  -- join to all terms after calendardate
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

    iready_dr as (
        select
            student_id,
            academic_year_int,
            subject,
            most_recent_overall_relative_placement,
        from {{ ref("base_iready__diagnostic_results") }}
    ),

    iready as (
        select student_id, academic_year_int, iready_reading_recent, iready_math_recent,
        from
            iready_dr pivot (
                max(most_recent_overall_relative_placement) for subject
                in ('Reading' as iready_reading_recent, 'Math' as iready_math_recent)
            )
    ),

    ps_log as (
        select
            lg._dbt_source_relation,
            lg.studentid,
            lg.academic_year,
            lg.entry_date,
            lg.entry,
        from {{ ref("stg_powerschool__log") }} as lg
        inner join
            {{ ref("stg_powerschool__gen") }} as g
            on lg.logtypeid = g.id
            and g.cat = 'logtype'
            and g.name = 'Exempt from retention'
    ),

    exempt_override as (
        select
            _dbt_source_relation,
            studentid,
            academic_year,
            entry_date,
            entry,

            row_number() over (
                partition by _dbt_source_relation, studentid, academic_year
                order by entry_date desc
            ) as rn_log,
        from ps_log
    ),

    promo as (
        select
            co.student_number,
            co.academic_year,
            co.grade_level,
            co.is_self_contained,
            co.special_education_code,

            rt.term_name,

            att.ada_term_running,
            att.n_absences_y1_running,
            att.n_absences_y1_running_non_susp,

            ir.iready_reading_recent,
            ir.iready_math_recent,

            c.n_failing,
            c.projected_credits_y1_term,
            c.projected_credits_cum,

            case
                when
                    co.grade_level < 3
                    and co.is_self_contained
                    and co.special_education_code in ('CMI', 'CMO', 'CSE')
                then 'Exempt - Special Education'
                when
                    co.grade_level between 3 and 8
                    and (
                        nj.state_assessment_name = '3'
                        or nj.math_state_assessment_name in ('3', '4')
                    )
                then 'Exempt - Special Education'
                when lg.entry_date is not null
                then 'Exempt - Manual Override'
            end as exemption,

            case
                /* Gr K-8 */
                when co.grade_level <= 8 and att.ada_term_running is null
                then 'Off-Track'
                /* Gr K */
                when co.grade_level = 0 and att.ada_term_running < 0.75
                then 'Off-Track'
                /* Gr 1-2 */
                when co.grade_level between 1 and 2 and att.ada_term_running < 0.80
                then 'Off-Track'
                /* Gr3-8 */
                when co.grade_level between 3 and 8 and att.ada_term_running < 0.85
                then 'Off-Track'
                /* HS */
                when
                    co.grade_level >= 9
                    and att.n_absences_y1_running_non_susp >= att.hs_at_risk_absences
                then 'Off-Track'
                when
                    co.grade_level >= 9
                    and att.n_absences_y1_running_non_susp >= att.hs_off_track_absences
                then 'Off-Track'
                else 'On-Track'
            end as attendance_status,

            case
                /* Gr K-8 */
                when co.grade_level <= 8 and att.ada_term_running is null
                then 'Off-Track'
                /* Gr K */
                when co.grade_level = 0 and att.ada_term_running < 0.75
                then 'Off-Track'
                /* Gr 1-2 */
                when co.grade_level between 1 and 2 and att.ada_term_running < 0.80
                then 'Off-Track'
                /* Gr3-8 */
                when co.grade_level between 3 and 8 and att.ada_term_running < 0.85
                then 'Off-Track'
                /* HS */
                when
                    co.grade_level >= 9
                    and att.n_absences_y1_running_non_susp >= att.hs_at_risk_absences
                then 'Off-Track (Already reached threshold)'
                when
                    co.grade_level >= 9
                    and att.n_absences_y1_running_non_susp >= att.hs_off_track_absences
                then 'Off-Track (Approaching threshold)'
                else 'On-Track'
            end as attendance_status_hs_detail,

            case
                /* Gr1-2 */
                when
                    co.grade_level between 1 and 2
                    and coalesce(ir.iready_reading_recent, '')
                    in ('2 Grade Levels Below', '3 or More Grade Levels Below', '')
                then 'Off-Track'
                /* Gr3-8 */
                when
                    co.grade_level between 3 and 8
                    and coalesce(ir.iready_reading_recent, '')
                    in ('2 Grade Levels Below', '3 or More Grade Levels Below', '')
                    and coalesce(ir.iready_math_recent, '')
                    in ('2 Grade Levels Below', '3 or More Grade Levels Below', '')
                then 'Off-Track'
                /* HS */
                when co.grade_level = 9 and c.projected_credits_cum < 25
                then 'Off-Track'
                when co.grade_level = 10 and c.projected_credits_cum < 50
                then 'Off-Track'
                when co.grade_level = 11 and c.projected_credits_cum < 85
                then 'Off-Track'
                when co.grade_level = 12 and c.projected_credits_cum < 120
                then 'Off-Track'
                else 'On-Track'
            end as academic_status,
        from {{ ref("base_powerschool__student_enrollments") }} as co
        cross join (select *, from unnest(['Q1', 'Q2', 'Q3', 'Q4']) as term_name) as rt
        left join
            attendance as att
            on co.studentid = att.studentid
            and co.yearid = att.yearid
            and rt.term_name = att.term_name
            and {{ union_dataset_join_clause(left_alias="co", right_alias="att") }}
        left join
            credits as c
            on co.studentid = c.studentid
            and co.academic_year = c.academic_year
            and rt.term_name = c.storecode
            and {{ union_dataset_join_clause(left_alias="co", right_alias="c") }}
        left join
            iready as ir
            on co.student_number = ir.student_id
            and co.academic_year = ir.academic_year_int
        left join
            {{ ref("stg_powerschool__s_nj_stu_x") }} as nj
            on co.students_dcid = nj.studentsdcid
            and {{ union_dataset_join_clause(left_alias="co", right_alias="nj") }}
        left join
            exempt_override as lg
            on co.studentid = lg.studentid
            and {{ union_dataset_join_clause(left_alias="co", right_alias="lg") }}
            and co.academic_year = lg.academic_year
            and lg.rn_log = 1
        where co.rn_year = 1
    )

select
    student_number,
    academic_year,
    term_name,
    ada_term_running,
    n_absences_y1_running,
    n_absences_y1_running_non_susp,
    iready_reading_recent,
    iready_math_recent,
    n_failing,
    projected_credits_cum,
    projected_credits_y1_term,
    attendance_status,
    attendance_status_hs_detail,
    academic_status,
    exemption,
    case
        when grade_level = 0
        then attendance_status
        when
            grade_level between 1 and 8
            and academic_status = 'Off-Track'
            and attendance_status = 'Off-Track'
        then 'Off-Track'
        when
            grade_level >= 9
            and (academic_status = 'Off-Track' or attendance_status = 'Off-Track')
        then 'Off-Track'
        else 'On-Track'
    end as overall_status,
from promo

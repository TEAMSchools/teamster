with
    attendance as (
        select
            mem._dbt_source_relation,
            mem.studentid,
            mem.yearid,
            round(avg(mem.attendancevalue), 2) as ada_term_running,
            coalesce(sum(abs(mem.attendancevalue - 1)), 0) as n_absences_y1_running,

            rt.name as term_name,
        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }} as mem
        inner join
            {{ ref("stg_reporting__terms") }} as rt
            on mem.schoolid = rt.school_id
            and mem.yearid = rt.powerschool_year_id
            and mem.calendardate <= rt.end_date  -- join to all terms after calendardate
            and rt.type = 'RT'
        where
            mem.membershipvalue = 1
            and mem.calendardate
            between date({{ var("current_academic_year") }}, 7, 1) and current_date(
                'America/New_York'
            )
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

    promo as (
        select
            co.student_number,
            co.academic_year,
            co.school_level,
            co.grade_level,
            case
                when co.school_level = 'HS' and co.region = 'Newark'
                then 27
                when co.school_level = 'HS' and co.region = 'Camden'
                then 36
            end as hs_attendance_cutoffs,
            case
                when co.grade_level = 9
                then 25
                when co.grade_level = 10
                then 50
                when co.grade_level = 11
                then 85
                when co.grade_level = 12
                then 120
            end as hs_credit_requirements,

            rt.name as term_name,
            rt.is_current,

            att.ada_term_running,
            att.n_absences_y1_running,

            ir.iready_reading_recent,
            ir.iready_math_recent,

            if(co.grade_level >= 5, c.n_failing, null) as n_failing,
            if(
                co.school_level = 'HS', c.projected_credits_y1_term, null
            ) as projected_credits_y1_term,
            if(
                co.school_level = 'HS', c.projected_credits_cum, null
            ) as projected_credits_cum,

            case
                /* Gr K-8 */
                when co.grade_level <= 8 and att.ada_term_running is null
                then 'At-Risk'
                /* Gr K */
                when co.grade_level = 0 and att.ada_term_running < 0.75
                then 'At-Risk'
                when co.grade_level = 0 and att.ada_term_running < 0.85
                then 'Off-Track'
                /* Gr 1-2 */
                when co.grade_level between 1 and 2 and att.ada_term_running < 0.80
                then 'At-Risk'
                when co.grade_level between 1 and 2 and att.ada_term_running < 0.90
                then 'Off-Track'
                /* Gr3-8 */
                when co.grade_level between 3 and 8 and att.ada_term_running < 0.85
                then 'At-Risk'
                when co.grade_level between 3 and 8 and att.ada_term_running < 0.90
                then 'Off-Track'
                /* HS */
                when
                    co.school_level = 'HS'
                    and (
                        (co.region = 'Newark' and att.n_absences_y1_running >= 27)
                        or (co.region = 'Camden' and att.n_absences_y1_running >= 36)
                    )
                then 'At-Risk'
                when
                    co.school_level = 'HS'
                    and rt.name = 'Q1'
                    and (
                        (co.region = 'Newark' and att.n_absences_y1_running >= 6)
                        or (co.region = 'Camden' and att.n_absences_y1_running >= 9)
                    )
                then 'Off-Track'
                when
                    co.school_level = 'HS'
                    and rt.name = 'Q2'
                    and (
                        (co.region = 'Newark' and att.n_absences_y1_running >= 12)
                        or (co.region = 'Camden' and att.n_absences_y1_running >= 18)
                    )
                then 'Off-Track'
                when
                    co.school_level = 'HS'
                    and rt.name = 'Q3'
                    and (
                        (co.region = 'Newark' and att.n_absences_y1_running >= 18)
                        or (co.region = 'Camden' and att.n_absences_y1_running >= 27)
                    )
                then 'Off-Track'
                else 'On-Track'
            end as attendance_status,

            case
                when co.grade_level = 0
                then 'N/A'
                /* Gr1-2 */
                when
                    co.grade_level between 1 and 2
                    and (
                        ir.iready_reading_recent
                        in ('2 Grade Levels Below', '3 or More Grade Levels Below')
                        or ir.iready_reading_recent is null
                    )
                then 'At-Risk'
                when
                    co.grade_level between 1 and 2
                    and ir.iready_reading_recent = '1 Grade Level Below'
                then 'Off-Track'
                /* Gr3-8 */
                when
                    co.grade_level between 3 and 8
                    and (
                        ir.iready_reading_recent
                        in ('2 Grade Levels Below', '3 or More Grade Levels Below')
                        or ir.iready_reading_recent is null
                    )
                    and (
                        ir.iready_math_recent
                        in ('2 Grade Levels Below', '3 or More Grade Levels Below')
                        or ir.iready_math_recent is null
                    )
                then 'At-Risk'
                when
                    co.grade_level between 3 and 8
                    and (
                        ir.iready_reading_recent
                        in ('2 Grade Levels Below', '3 or More Grade Levels Below')
                        or ir.iready_reading_recent is null
                    )
                    and (
                        ir.iready_math_recent
                        in ('2 Grade Levels Below', '3 or More Grade Levels Below')
                        or ir.iready_math_recent is null
                    )
                then 'Off-Track'
                /* HS */
                when
                    co.grade_level = 9
                    and coalesce(gc.earned_credits_cum, 0)
                    + coalesce(c.projected_credits_y1_term, 0)
                    < 25
                then 'At-Risk'
                when
                    co.grade_level = 10
                    and coalesce(gc.earned_credits_cum, 0)
                    + coalesce(c.projected_credits_y1_term, 0)
                    < 50
                then 'At-Risk'
                when
                    co.grade_level = 11
                    and coalesce(gc.earned_credits_cum, 0)
                    + coalesce(c.projected_credits_y1_term, 0)
                    < 85
                then 'At-Risk'
                when
                    co.grade_level = 12
                    and coalesce(gc.earned_credits_cum, 0)
                    + coalesce(c.projected_credits_y1_term, 0)
                    < 120
                then 'At-Risk'
                else 'On-Track'
            end as academic_status,
        from {{ ref("base_powerschool__student_enrollments") }} as co
        inner join
            {{ ref("stg_reporting__terms") }} as rt
            on co.academic_year = rt.academic_year
            and co.schoolid = rt.school_id
            and rt.type = 'RT'
        left join
            attendance as att
            on co.studentid = att.studentid
            and co.yearid = att.yearid
            and rt.name = att.term_name
            and {{ union_dataset_join_clause(left_alias="co", right_alias="att") }}
        left join
            credits as c
            on co.studentid = c.studentid
            and co.academic_year = c.academic_year
            and rt.name = c.storecode
            and {{ union_dataset_join_clause(left_alias="co", right_alias="c") }}
        left join
            iready as ir
            on co.student_number = ir.student_id
            and co.academic_year = ir.academic_year_int
        where co.academic_year = {{ var("current_academic_year") }} and co.rn_year = 1
    )

select
    student_number,
    academic_year,
    school_level,
    grade_level,
    term_name,
    is_current,
    ada_term_running,
    n_absences_y1_running,
    hs_attendance_cutoffs,
    iready_reading_recent,
    iready_math_recent,
    n_failing,
    projected_credits_y1_term,
    projected_credits_cum,
    hs_credit_requirements,
    attendance_status,
    academic_status,
    case
        when grade_level = 0
        then attendance_status
        when
            grade_level between 1 and 8
            and (academic_status = 'At-Risk' and attendance_status = 'At-Risk')
        then 'At-Risk'
        when
            grade_level between 1 and 8
            and (academic_status != 'On-Track' or attendance_status != 'On-Track')
        then 'Off-Track'
        when
            school_level = 'HS'
            and (academic_status = 'At-Risk' or attendance_status = 'At-Risk')
        then 'At-Risk'
        when
            school_level = 'HS'
            and (academic_status != 'At-Risk' and attendance_status = 'Off-Track')
        then 'Off-Track'
        else 'On-Track'
    end as overall_status,
from promo

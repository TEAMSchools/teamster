with
    attendance as (
        select
            mem._dbt_source_relation,
            mem.studentid,
            mem.yearid,
            round(avg(mem.attendancevalue), 2) as ada_term_running,
            coalesce(sum(abs(mem.attendancevalue - 1)), 0) as n_absences_y1_running,

            rt.name as term,
        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }} as mem
        inner join
            {{ ref("stg_reporting__terms") }} as rt
            on mem.calendardate <= rt.end_date
            and mem.schoolid = rt.school_id
            and mem.yearid = rt.powerschool_year_id
            and rt.type = 'RT'
        where
            mem.membershipvalue = 1
            and mem.calendardate <= current_date('America/New_York')
        group by mem._dbt_source_relation, mem.yearid, mem.studentid, rt.name
    ),

    credits as (
        select
            _dbt_source_relation,
            studentid,
            academic_year,
            storecode,
            sum(potential_credit_hours) as enrolled_credit_hours,
            sum(if(y1_letter_grade_adjusted in ('F', 'F*'), 1, 0)) as n_failing,
            sum(
                if(
                    y1_letter_grade_adjusted not in ('F', 'F*')
                    and y1_letter_grade_adjusted is not null,
                    potential_credit_hours,
                    null
                )
            ) as projected_credits_y1_term,
        from {{ ref("base_powerschool__final_grades") }}
        group by _dbt_source_relation, studentid, academic_year, storecode
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
    )

select
    co.student_number,
    co.lastfirst,
    co.region,
    co.school_level,
    co.school_abbreviation,
    co.grade_level,
    co.advisory_name,
    co.advisor_lastfirst as advisor_name,
    co.lep_status,
    co.ethnicity,
    co.gender,
    co.is_retained_year,
    co.is_retained_ever,
    case when co.spedlep like 'SPED%' then 'Has IEP' else co.spedlep end as iep_status,

    rt.name as term,
    rt.is_current,

    att.ada_term_running,
    att.n_absences_y1_running,

    ir.iready_reading_recent,
    ir.iready_math_recent,

    if(co.grade_level > 4, c.n_failing, null) as n_failing,
    if(
        co.school_level = 'HS', c.projected_credits_y1_term, null
    ) as projected_credits_y1_term,
    if(
        co.school_level = 'HS',
        coalesce(gc.earned_credits_cum, 0) + coalesce(c.projected_credits_y1_term, 0),
        null
    ) as projected_credits_cum,

    case
        /* Kinder */
        when
            co.grade_level = 0
            and (round(att.ada_term_running, 2) < 0.75 or att.ada_term_running is null)
        then 'Retain'
        when co.grade_level = 0 and round(att.ada_term_running, 2) between 0.76 and 0.84
        then 'At-Risk (ADA)'
        /* Gr1-2 */
        when
            co.grade_level between 1 and 2
            and (round(att.ada_term_running, 2) < 0.80 or att.ada_term_running is null)
            and (
                ir.iready_reading_recent
                in ('2 Grade Levels Below', '3 or More Grade Levels Below')
                or ir.iready_reading_recent is null
            )
        then 'Retain'
        when
            co.grade_level between 1 and 2
            and (round(att.ada_term_running, 2) < 0.90 or att.ada_term_running is null)
        then 'At-Risk (ADA)'
        when
            co.grade_level between 1 and 2
            and (
                ir.iready_reading_recent
                in ('2 Grade Levels Below', '3 or More Grade Levels Below')
                or ir.iready_reading_recent is null
            )
        then 'At-Risk (i-Ready)'
        /* Gr3-8 */
        when
            co.grade_level between 3 and 8
            and (round(att.ada_term_running, 2) < 0.85 or att.ada_term_running is null)
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
        then 'Retain'
        when
            co.grade_level between 3 and 8
            and (round(att.ada_term_running, 2) < 0.90 or att.ada_term_running is null)
        then 'At-Risk (ADA)'
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
        then 'At-Risk (i-Ready)'
        /* HS */
        when
            co.grade_level = 9
            and (
                coalesce(gc.earned_credits_cum, 0)
                + coalesce(c.projected_credits_y1_term, 0)
                < 25
                or (
                    (co.region = 'Newark' and att.n_absences_y1_running >= 27)
                    or (co.region = 'Camden' and att.n_absences_y1_running >= 36)
                )
            )
        then 'Retain'
        when
            co.grade_level = 10
            and (
                coalesce(gc.earned_credits_cum, 0)
                + coalesce(c.projected_credits_y1_term, 0)
                < 50
                or (
                    (co.region = 'Newark' and att.n_absences_y1_running >= 27)
                    or (co.region = 'Camden' and att.n_absences_y1_running >= 36)
                )
            )
        then 'Retain'
        when
            co.grade_level = 11
            and (
                coalesce(gc.earned_credits_cum, 0)
                + coalesce(c.projected_credits_y1_term, 0)
                < 85
                or (
                    (co.region = 'Newark' and att.n_absences_y1_running >= 27)
                    or (co.region = 'Camden' and att.n_absences_y1_running >= 36)
                )
            )
        then 'Retain'
        when
            co.grade_level = 12
            and (
                coalesce(gc.earned_credits_cum, 0)
                + coalesce(c.projected_credits_y1_term, 0)
                < 120
                or (
                    (co.region = 'Newark' and att.n_absences_y1_running >= 27)
                    or (co.region = 'Camden' and att.n_absences_y1_running >= 36)
                )
            )
        then 'Retain'
        when
            co.grade_level = 12
            and coalesce(gc.earned_credits_cum, 0)
            + coalesce(c.projected_credits_y1_term, 0)
            >= 120
            and (
                (co.region = 'Newark' and att.n_absences_y1_running < 27)
                or (co.region = 'Camden' and att.n_absences_y1_running < 36)
            )
        then 'Graduate (pending other requirements)'
        when
            co.school_level = 'HS'
            and rt.name = 'Q1'
            and (
                (co.region = 'Newark' and att.n_absences_y1_running >= 6)
                or (co.region = 'Camden' and att.n_absences_y1_running >= 9)
            )
        then 'At-Risk (Absences)'
        when
            co.school_level = 'HS'
            and rt.name = 'Q2'
            and (
                (co.region = 'Newark' and att.n_absences_y1_running >= 12)
                or (co.region = 'Camden' and att.n_absences_y1_running >= 18)
            )
        then 'At-Risk (Absences)'
        when
            co.school_level = 'HS'
            and rt.name = 'Q3'
            and (
                (co.region = 'Newark' and att.n_absences_y1_running >= 18)
                or (co.region = 'Camden' and att.n_absences_y1_running >= 27)
            )
        then 'At-Risk (Absences)'
        else 'Promote'
    end as promo_status_overall,
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
    and rt.name = att.term
    and {{ union_dataset_join_clause(left_alias="co", right_alias="att") }}
left join
    credits as c
    on co.studentid = c.studentid
    and co.academic_year = c.academic_year
    and rt.name = c.storecode
    and {{ union_dataset_join_clause(left_alias="co", right_alias="c") }}
left join
    {{ ref("int_powerschool__gpa_cumulative") }} as gc
    on co.studentid = gc.studentid
    and co.schoolid = gc.schoolid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="gc") }}
left join
    iready as ir
    on co.student_number = ir.student_id
    and co.academic_year = ir.academic_year_int
where
    co.academic_year = {{ var("current_academic_year") }}
    and co.rn_year = 1
    and co.enroll_status = 0

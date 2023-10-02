with
    ada as (
        select
            mem._dbt_source_relation,
            mem.yearid,
            mem.studentid,
            rt.name as term,
            round(avg(mem.attendancevalue), 2) as ada_term_running,
            coalesce(sum(abs(mem.attendancevalue - 1)), 0) as n_absences_y1_running
        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }} as mem
        inner join
            {{ ref("base_powerschool__student_enrollments") }} as co
            on mem.studentid = co.studentid
            and mem.yearid = co.yearid
            and (mem.calendardate between co.entrydate and co.exitdate)
            and co.rn_year = 1
            and {{ union_dataset_join_clause(left_alias="mem", right_alias="co") }}
        inner join
            {{ ref("stg_reporting__terms") }} as rt
            on (
                mem.calendardate <= rt.end_date
                and mem.schoolid = rt.school_id
                and mem.yearid + 1990 = rt.academic_year
                and rt.type = 'RT'
            )
        where
            mem.membershipvalue = 1 and calendardate <= current_date('America/New_York')
        group by mem._dbt_source_relation, mem.yearid, mem.studentid, rt.name
    ),
    terms as (select term from unnest(['Q1', 'Q2', 'Q3', 'Q4']) as term),
    credits as (
        select
            fg.studentid,
            fg._dbt_source_relation,
            fg.academic_year,
            fg.storecode,
            sum(
                case when fg.y1_letter_grade_adjusted in ('F', 'F*') then 1 else 0 end
            ) as n_failing,
            sum(
                case
                    when
                        fg.y1_letter_grade_adjusted not in ('F', 'F*')
                        and fg.y1_letter_grade_adjusted is not null
                    then fg.potential_credit_hours
                end
            ) as projected_credits_y1_term,
            sum(fg.potential_credit_hours) as enrolled_credit_hours
        from {{ ref("base_powerschool__final_grades") }} as fg
        group by fg.studentid, fg._dbt_source_relation, fg.academic_year, fg.storecode
    ),
    absences as (
        select
            co.student_number,
            co.academic_year,
            coalesce(sum(abs(attendancevalue - 1)), 0) as n_absences_y1
        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }} as mem
        inner join
            {{ ref("base_powerschool__student_enrollments") }} as co
            on mem.studentid = co.studentid
            and mem.yearid = co.yearid
            and (mem.calendardate between co.entrydate and co.exitdate)
            and co.rn_year = 1
            and {{ union_dataset_join_clause(left_alias="mem", right_alias="co") }}
        where mem.membershipvalue = 1
        group by co.student_number, co.academic_year
    ),
    iready as (
        select
            student_number,
            academic_year,
            reading as iready_reading_recent,
            math as iready_math_recent
        from
            (
                select
                    student_id as student_number,
                    academic_year_int as academic_year,
                    subject,
                    most_recent_overall_relative_placement
                from {{ ref("base_iready__diagnostic_results") }}
            ) pivot (
                max(most_recent_overall_relative_placement) for subject
                in ('Reading', 'Math')
            ) as p
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
    case when co.spedlep like 'SPED%' then 'Has IEP' else co.spedlep end as iep_status,
    co.lep_status,
    co.ethnicity,
    co.gender,
    co.is_retained_year,
    co.is_retained_ever,
    terms.term,
    rt.is_current,
    ada.ada_term_running,
    ada.n_absences_y1_running,
    (case when co.grade_level > 4 then c.n_failing end) as n_failing,
    (
        case when co.school_level = 'HS' then c.projected_credits_y1_term end
    ) as projected_credits_y1_term,
    (
        case
            when co.school_level = 'HS'
            then
                (
                    coalesce(gc.earned_credits_cum, 0)
                    + coalesce(c.projected_credits_y1_term, 0)
                )
        end
    ) as projected_credits_cum,
    ir.iready_reading_recent,
    ir.iready_math_recent,
    (
        case  /* Kinder */
            when
                co.grade_level = 0
                and (
                    round(ada.ada_term_running, 2) < .75 or ada.ada_term_running is null
                )
            then 'Retain'
            when
                co.grade_level = 0
                and (round(ada.ada_term_running, 2) between .76 and .84)
            then 'At-Risk (ADA)'  /* Gr1-2 */
            when
                (co.grade_level between 1 and 2)
                and (
                    round(ada.ada_term_running, 2) < .80 or ada.ada_term_running is null
                )
                and (
                    ir.iready_reading_recent
                    in ('2 Grade Levels Below', '3 or More Grade Levels Below')
                    or ir.iready_reading_recent is null
                )
            then 'Retain'
            when
                (co.grade_level between 1 and 2)
                and (
                    round(ada.ada_term_running, 2) < .90 or ada.ada_term_running is null
                )
            then 'At-Risk (ADA)'
            when
                (co.grade_level between 1 and 2)
                and (
                    ir.iready_reading_recent
                    in ('2 Grade Levels Below', '3 or More Grade Levels Below')
                    or ir.iready_reading_recent is null
                )
            then 'At-Risk (i-Ready)'  /* Gr3-8 */
            when
                (co.grade_level between 3 and 8)
                and (
                    round(ada.ada_term_running, 2) < .85 or ada.ada_term_running is null
                )
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
                (co.grade_level between 3 and 8)
                and (
                    round(ada.ada_term_running, 2) < .90 or ada.ada_term_running is null
                )
            then 'At-Risk (ADA)'
            when
                (co.grade_level between 3 and 8)
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
            then 'At-Risk (i-Ready)'  /* HS */
            when
                co.grade_level = 9
                and (
                    coalesce(gc.earned_credits_cum, 0)
                    + coalesce(c.projected_credits_y1_term, 0)
                )
                < 25
                or (
                    (co.region = 'Newark' and ada.n_absences_y1_running >= 27)
                    or (co.region = 'Camden' and ada.n_absences_y1_running >= 36)
                )
            then 'Retain'
            when
                co.grade_level = 10
                and (
                    coalesce(gc.earned_credits_cum, 0)
                    + coalesce(c.projected_credits_y1_term, 0)
                )
                < 50
                or (
                    (co.region = 'Newark' and ada.n_absences_y1_running >= 27)
                    or (co.region = 'Camden' and ada.n_absences_y1_running >= 36)
                )
            then 'Retain'
            when
                co.grade_level = 11
                and (
                    coalesce(gc.earned_credits_cum, 0)
                    + coalesce(c.projected_credits_y1_term, 0)
                )
                < 85
                or (
                    (co.region = 'Newark' and ada.n_absences_y1_running >= 27)
                    or (co.region = 'Camden' and ada.n_absences_y1_running >= 36)
                )
            then 'Retain'
            when
                co.grade_level = 12
                and (
                    coalesce(gc.earned_credits_cum, 0)
                    + coalesce(c.projected_credits_y1_term, 0)
                )
                < 120
                or (
                    (co.region = 'Newark' and ada.n_absences_y1_running >= 27)
                    or (co.region = 'Camden' and ada.n_absences_y1_running >= 36)
                )
            then 'Retain'
            when
                co.grade_level = 12
                and (
                    coalesce(gc.earned_credits_cum, 0)
                    + coalesce(c.projected_credits_y1_term, 0)
                )
                >= 120
                and (
                    (co.region = 'Newark' and ada.n_absences_y1_running < 27)
                    or (co.region = 'Camden' and ada.n_absences_y1_running < 36)
                )
            then 'Graduate (pending other requirements)'
            when
                co.school_level = 'HS'
                and terms.term = 'Q1'
                and (
                    (co.region = 'Newark' and ada.n_absences_y1_running >= 6)
                    or (co.region = 'Camden' and ada.n_absences_y1_running >= 9)
                )
            then 'At-Risk (Absences)'
            when
                co.school_level = 'HS'
                and terms.term = 'Q2'
                and (
                    (co.region = 'Newark' and ada.n_absences_y1_running >= 12)
                    or (co.region = 'Camden' and ada.n_absences_y1_running >= 18)
                )
            then 'At-Risk (Absences)'
            when
                co.school_level = 'HS'
                and terms.term = 'Q3'
                and (
                    (co.region = 'Newark' and ada.n_absences_y1_running >= 18)
                    or (co.region = 'Camden' and ada.n_absences_y1_running >= 27)
                )
            then 'At-Risk (Absences)'
            else 'Promote'
        end
    ) as promo_status_overall,
from {{ ref("base_powerschool__student_enrollments") }} as co
cross join terms
left join
    ada
    on (
        ada.studentid = co.studentid
        and ada.yearid = co.yearid
        and ada.term = terms.term
        and {{ union_dataset_join_clause(left_alias="co", right_alias="ada") }}
    )
left join
    credits as c
    on co.studentid = c.studentid
    and co.academic_year = c.academic_year
    and terms.term = c.storecode
    and {{ union_dataset_join_clause(left_alias="co", right_alias="c") }}
left join
    {{ ref("int_powerschool__gpa_cumulative") }} as gc
    on co.studentid = gc.studentid
    and co.schoolid = gc.schoolid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="gc") }}
left join
    iready as ir
    on co.student_number = ir.student_number
    and co.academic_year = ir.academic_year
inner join
    {{ ref("stg_reporting__terms") }} as rt
    on (
        co.academic_year = rt.academic_year
        and co.schoolid = rt.school_id
        and terms.term = rt.name
        and rt.type = 'RT'
    )
where
    co.academic_year = {{ var("current_academic_year") }}
    and co.rn_year = 1
    and co.enroll_status = 0

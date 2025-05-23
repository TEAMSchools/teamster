with
    gpa_and_grade_level as (
        select
            e._dbt_source_relation,
            e.academic_year,
            e.yearid,
            e.student_number,
            e.students_dcid,
            e.studentid,
            e.grade_level,
            e.grade_level_prev,

            term,

            g.gpa_term,
            gc.gpa_y1 as q2_y1_gpa,
            gp.gpa_y1 as py_gpa,

            if(
                e.grade_level = 9
                and (e.grade_level_prev <= 8 or e.grade_level_prev is null),
                true,
                false
            ) as is_first_time_ninth,

        from {{ ref("int_extracts__student_enrollments") }} as e
        cross join unnest(['Q1', 'Q2']) as term
        left join
            {{ ref("int_powerschool__gpa_term") }} as g
            on e.studentid = g.studentid
            and e.yearid = g.yearid
            and term = g.term_name
            and {{ union_dataset_join_clause(left_alias="e", right_alias="g") }}
        left join
            {{ ref("int_powerschool__gpa_term") }} as gc
            on g.studentid = gc.studentid
            and g.yearid = gc.yearid
            and {{ union_dataset_join_clause(left_alias="g", right_alias="gc") }}
            and gc.term_name = 'Q2'
        left join
            {{ ref("int_powerschool__gpa_term") }} as gp
            on g.studentid = gp.studentid
            and g.yearid - 1 = gp.yearid
            and {{ union_dataset_join_clause(left_alias="g", right_alias="gp") }}
            and gp.is_current
        where
            e.enroll_status = 0
            and e.grade_level >= 9
            and e.academic_year = {{ var("current_academic_year") }}
    ),

    gpa_and_grade_level_component as (
        select
            _dbt_source_relation,
            academic_year,
            yearid,
            student_number,
            students_dcid,
            studentid,
            grade_level,
            grade_level_prev,
            is_first_time_ninth,
            py_gpa,
            q2_y1_gpa,

            case
                when is_first_time_ninth
                then 'Eligible'
                when py_gpa is null
                then 'No PY GPA'
                when py_gpa >= 2.5
                then 'Eligible'
                when py_gpa >= 2.2 and py_gpa <= 2.49
                then 'Probation'
                else 'Ineligible'
            end as q1_gpa_eligibility_status,

            case
                when q1 is null
                then 'No Q1 GPA'
                when q1 >= 2.5
                then 'Eligible'
                when q1 >= 2.2 and q1 <= 2.49
                then 'Probation'
                else 'Ineligible'
            end as q2_gpa_eligibility_status,

            case
                when q2_y1_gpa is null
                then 'No S1 GPA'
                when q2_y1_gpa >= 2.5
                then 'Eligible'
                when q2_y1_gpa >= 2.2 and q2_y1_gpa <= 2.49
                then 'Probation'
                else 'Ineligible'
            end as s2_gpa_eligibility_status,

        from gpa_and_grade_level pivot (avg(gpa_term) for term in ('Q1', 'Q2'))
    ),

    credits as (
        select
            _dbt_source_relation,
            studentsdcid,
            studentid,
            academic_year,
            cc_dcid,
            course_number,
            is_transfer_grade,
            credit_status,
            official_potential_credits,

            if(earned_credits = 0.0, 0.0, official_potential_credits) as credits_earned,

            if(
                academic_year = {{ var("current_academic_year") }}, true, false
            ) as is_current_academic_year,

            if(
                academic_year = {{ var("current_academic_year") - 1 }}, true, false
            ) as is_previous_academic_year,

        from {{ ref("int_powerschool__gpprogress_grades") }}
        where plan_name = 'NJ State Diploma'
    ),

    yearly_credits as (
        select
            *,

            sum(credits_earned) over (
                partition by _dbt_source_relation, academic_year, studentsdcid
            ) as academic_year_credits_earned,

            sum(official_potential_credits) over (
                partition by _dbt_source_relation, academic_year, studentsdcid
            ) as academic_year_credits_potential,

        from credits
    ),

    custom_yearly_credits as (
        select
            _dbt_source_relation,
            studentsdcid,

            avg(
                case
                    when is_previous_academic_year then academic_year_credits_earned
                end
            ) as earned_credits_previous_year,

            avg(
                case when is_current_academic_year then academic_year_credits_earned end
            ) as earned_credits_current_year,

            avg(
                case
                    when is_current_academic_year
                    then (0.5 * academic_year_credits_earned)
                end
            ) as half_earned_credits_current_year,

            avg(
                case
                    when is_current_academic_year then academic_year_credits_potential
                end
            ) as potential_credits_current_year,

        from yearly_credits
        group by _dbt_source_relation, studentsdcid
    ),

    credits_component as (
        select
            c._dbt_source_relation,
            c.academic_year,
            c.studentsdcid,
            c.studentid,

            cy.earned_credits_previous_year,
            cy.earned_credits_current_year,
            cy.half_earned_credits_current_year,
            cy.potential_credits_current_year,

            c.academic_year - 1990 as yearid,

            if(
                cy.earned_credits_previous_year >= 30, true, false
            ) as is_py_credits_on_track,

            if(
                cy.potential_credits_current_year / 2
                = cy.half_earned_credits_current_year,
                true,
                false
            ) as is_cy_credits_on_track,

        from credits as c
        inner join
            custom_yearly_credits as cy
            on c.studentsdcid = cy.studentsdcid
            and {{ union_dataset_join_clause(left_alias="c", right_alias="cy") }}
        where c.academic_year = {{ var("current_academic_year") }}
    ),

    term as (
        select
            t._dbt_source_relation,
            t.schoolid,
            t.yearid,

            tb.storecode as term,
            tb.date1 as term_start_date,
            tb.date2 as term_end_date,

            t.yearid + 1990 as academic_year,

            if(
                current_date('{{ var("local_timezone") }}')
                between tb.date1 and tb.date2,
                true,
                false
            ) as is_current_term,

            case
                when tb.storecode in ('Q1', 'Q2')
                then 'S1'
                when tb.storecode in ('Q3', 'Q4')
                then 'S2'
            end as semester,

        from {{ ref("stg_powerschool__terms") }} as t
        inner join
            {{ ref("stg_powerschool__termbins") }} as tb
            on t.id = tb.termid
            and t.schoolid = tb.schoolid
            and {{ union_dataset_join_clause(left_alias="t", right_alias="tb") }}
            and tb.storecode in ('Q1', 'Q2', 'Q3', 'Q4')
        where t.isyearrec = 1
    ),

    ada_py as (
        select
            _dbt_source_relation,
            yearid,
            studentid,

            yearid + 1990 as academic_year,

            avg(attendancevalue) as py_ada,

        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }}
        where
            membershipvalue = 1
            and calendardate <= current_date('{{ var("local_timezone") }}')
        group by _dbt_source_relation, yearid, studentid
    ),

    membership_days as (
        select
            a._dbt_source_relation,
            a.yearid,
            a.studentid,
            a.schoolid,
            a.membershipvalue,
            a.attendancevalue,

            t.academic_year,
            t.semester,
            t.term,

        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }} as a
        inner join
            term as t
            on a.yearid = t.yearid
            and a.schoolid = t.schoolid
            and {{ union_dataset_join_clause(left_alias="a", right_alias="t") }}
            and a.calendardate >= t.term_start_date
            and a.calendardate <= t.term_end_date
        where
            a.membershipvalue = 1
            and t.academic_year = {{ var("current_academic_year") }}
    ),

    ada_by_quarter as (
        select
            _dbt_source_relation,
            studentid,
            academic_year,
            yearid,
            semester,
            term,

            avg(attendancevalue) as quarter_ada,

        from membership_days
        group by _dbt_source_relation, academic_year, yearid, studentid, semester, term
    ),

    ada_by_semester as (
        select
            _dbt_source_relation,
            studentid,
            academic_year,
            yearid,
            semester,

            avg(attendancevalue) as semester_ada,

        from membership_days
        group by _dbt_source_relation, academic_year, yearid, studentid, semester
    ),

    ada_component as (
        select
            p._dbt_source_relation,
            p.studentid,
            p.academic_year,
            p.yearid,

            s.semester_ada as s1_ada,

            q1,

        from
            ada_by_quarter
            pivot (avg(quarter_ada) for term in ('Q1', 'Q2', 'Q3', 'Q4')) as p
        left join
            ada_by_semester as s
            on p.studentid = s.studentid
            and {{ union_dataset_join_clause(left_alias="p", right_alias="s") }}
            and s.semester = 'S1'
    )

select
    e._dbt_source_relation,
    e.academic_year,
    e.yearid,
    e.student_number,
    e.students_dcid,
    e.studentid,
    e.grade_level,
    e.grade_level_prev,
    e.term,
    e.gpa_term,
    e.py_gpa,

    c.earned_credits_previous_year,
    c.earned_credits_current_year,
    c.half_earned_credits_current_year,
    c.potential_credits_current_year,
    c.is_py_credits_on_track,
    c.is_cy_credits_on_track,

    a.semester,
    a.term,
    a.`ada`,

    case
        -- 9th grade exceptions
        when
            e.grade_level = 9
            and (e.grade_level_prev <= 8 or e.grade_level_prev is null)
            and a.term = 'Q1'
        then 'Eligible'
        when
            e.grade_level = 9
            and (e.grade_level_prev <= 8 or e.grade_level_prev is null)
            and a.term = 'Q2'
            and g.gpa_term >= 2.5
            and a.`ada` >= .9
        then 'Eligible'
        when
            e.grade_level = 9
            and (e.grade_level_prev <= 8 or e.grade_level_prev is null)
            and a.term = 'Q2'
            and g.gpa_term >= 2.5
            and a.`ada` < .9
        then 'Probabtion - ADA'
        when
            e.grade_level = 9
            and (e.grade_level_prev <= 8 or e.grade_level_prev is null)
            and a.term = 'Q2'
            and (g.gpa_term >= 2.2 and g.gpa_term <= 2.49)
            and a.`ada` >= .9
        then 'Probation - GPA'
        when
            e.grade_level = 9
            and (e.grade_level_prev <= 8 or e.grade_level_prev is null)
            and a.term = 'Q2'
            and (g.gpa_term >= 2.2 and g.gpa_term <= 2.49)
            and a.`ada` < .9
        then 'Probation - GPA and ADA'
        when
            e.grade_level = 9
            and (e.grade_level_prev <= 8 or e.grade_level_prev is null)
            and a.term = 'Q2'
            and g.gpa_term < 2.2
            and a.`ada` >= .9
        then 'Ineligible - GPA'
        when
            e.grade_level = 9
            and (e.grade_level_prev <= 8 or e.grade_level_prev is null)
            and a.term = 'Q2'
            and g.gpa_term < 2.2
            and a.`ada` < .9
        then 'Ineligible - GPA and ADA'

        -- Q1 conditions
        when
            a.term = 'Q1'
            and c.earned_credits_previous_year >= 30
            and gp.gpa_y1 >= 2.5
            and a.`ada` >= .9
        then 'Eligible'
        when
            a.term = 'Q1'
            and c.earned_credits_previous_year >= 30
            and gp.gpa_y1 >= 2.5
            and a.`ada` < .9
        then 'Probabtion - ADA'
        when
            a.term = 'Q1'
            and c.earned_credits_previous_year >= 30
            and (gp.gpa_y1 >= 2.2 and gp.gpa_y1 <= 2.49)
            and a.`ada` >= .9
        then 'Probation - GPA'
        when
            a.term = 'Q1'
            and c.earned_credits_previous_year >= 30
            and (gp.gpa_y1 >= 2.2 and gp.gpa_y1 <= 2.49)
            and a.`ada` < .9
        then 'Probation - GPA and ADA'
        when
            a.term = 'Q1'
            and c.earned_credits_previous_year < 30
            and gp.gpa_y1 >= 2.5
            and a.`ada` >= .9
        then 'Ineligible - Credits'
        when
            a.term = 'Q1'
            and c.earned_credits_previous_year >= 30
            and gp.gpa_y1 < 2.2
            and a.`ada` >= .9
        then 'Ineligible - GPA'

        -- Q2 conditions
        when
            a.term = 'Q2'
            and c.is_cy_credits_on_track
            and g.gpa_term >= 2.5
            and a.`ada` >= .9
        then 'Eligible'
        when
            a.term = 'Q2'
            and c.is_cy_credits_on_track
            and g.gpa_term >= 2.5
            and a.`ada` < .9
        then 'Probabtion - ADA'
        when
            a.term = 'Q2'
            and c.is_cy_credits_on_track
            and (g.gpa_term >= 2.2 and g.gpa_term <= 2.49)
            and a.`ada` >= .9
        then 'Probation - GPA'
        when
            a.term = 'Q2'
            and not c.is_cy_credits_on_track
            and (g.gpa_term >= 2.2 and g.gpa_term <= 2.49)
            and a.`ada` < .9
        then 'Probation - GPA and ADA'
        when
            a.term = 'Q2'
            and not c.is_cy_credits_on_track
            and g.gpa_term >= 2.5
            and a.`ada` >= .9
        then 'Ineligible - Credits'
        when
            a.term = 'Q2'
            and c.is_cy_credits_on_track
            and g.gpa_term < 2.2
            and a.`ada` >= .9
        then 'Ineligible - GPA'

        else 'New combination'
    end as quarter_athletic_eligibility_status,

from gpa_and_grade_level_component as e
left join credits_component as c on
left join
    ada_component as a
    on c.studentid = a.studentid
    and a.academic_year = c.academic_year
    and {{ union_dataset_join_clause(left_alias="c", right_alias="a") }}

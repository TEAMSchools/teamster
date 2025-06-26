with
    py_credits as (
        select
            _dbt_source_relation,
            yearid,
            studentid,

            if(sum(earnedcrhrs) >= 30, true, false) as met_py_credits,

        from {{ ref("stg_powerschool__storedgrades") }}
        where
            storecode = 'Y1' and academic_year = {{ var("current_academic_year") - 1 }}
        group by _dbt_source_relation, yearid, studentid
    ),

    cy_credits as (
        select
            _dbt_source_relation,
            yearid,
            studentid,

            if(
                sum(if(y1_letter_grade_adjusted in ('F', 'F*'), 1, 0)) = 0, true, false
            ) as met_cy_credits,

        from {{ ref("base_powerschool__final_grades") }}
        where storecode = 'Q2'
        group by _dbt_source_relation, yearid, studentid
    ),

    term as (
        select
            t._dbt_source_relation,
            t.schoolid,
            t.yearid,

            tb.storecode as term,

            t.yearid + 1990 as academic_year,

            if(
                current_date('America/New_York') between tb.date1 and tb.date2,
                true,
                false
            ) as is_current_term,

        from {{ ref("stg_powerschool__terms") }} as t
        inner join
            {{ ref("stg_powerschool__termbins") }} as tb
            on t.id = tb.termid
            and t.schoolid = tb.schoolid
            and {{ union_dataset_join_clause(left_alias="t", right_alias="tb") }}
            and tb.storecode in ('Q1', 'Q2', 'Q3', 'Q4')
        where t.isyearrec = 1
    ),

    base as (
        select
            e._dbt_source_relation,
            e.academic_year,
            e.yearid,
            e.schoolid,
            e.student_number,
            e.students_dcid,
            e.studentid,
            e.grade_level,
            e.grade_level_prev,
            e.dob,

            a.ada_term as cy_q1_ada,
            a.ada_semester as cy_s1_ada,

            apy.ada_year as py_y1_ada,

            gq1.gpa_term as cy_q1_gpa,

            gs1.gpa_y1 as cy_s1_gpa,

            gp.gpa_y1 as py_y1_gpa,

            pyc.met_py_credits,

            cyc.met_cy_credits,

            if(
                e.grade_level = 9
                and (e.grade_level_prev <= 8 or e.grade_level_prev is null),
                true,
                false
            ) as is_first_time_ninth,

            if(
                date_diff(date({{ var("current_academic_year") }}, 09, 01), e.dob, year)
                >= 19,
                false,
                true
            ) as is_age_eligible,

        from {{ ref("int_extracts__student_enrollments") }} as e
        left join
            {{ ref("int_powerschool__ada_term") }} as a
            on e.academic_year = a.academic_year
            and e.studentid = a.studentid
            and {{ union_dataset_join_clause(left_alias="e", right_alias="a") }}
            and a.term = 'Q1'
        left join
            {{ ref("int_powerschool__ada_term") }} as apy
            on e.academic_year - 1 = apy.academic_year
            and e.studentid = apy.studentid
            and {{ union_dataset_join_clause(left_alias="e", right_alias="apy") }}
            and apy.term = 'Q4'
        left join
            {{ ref("int_powerschool__gpa_term") }} as gq1
            on e.studentid = gq1.studentid
            and e.yearid = gq1.yearid
            and {{ union_dataset_join_clause(left_alias="e", right_alias="gq1") }}
            and gq1.term_name = 'Q1'
        left join
            {{ ref("int_powerschool__gpa_term") }} as gs1
            on e.studentid = gs1.studentid
            and e.yearid = gs1.yearid
            and {{ union_dataset_join_clause(left_alias="e", right_alias="gs1") }}
            and gs1.term_name = 'Q2'
        left join
            {{ ref("int_powerschool__gpa_term") }} as gp
            on e.studentid = gp.studentid
            and e.yearid - 1 = gp.yearid
            and {{ union_dataset_join_clause(left_alias="e", right_alias="gp") }}
            and gp.is_current
        left join
            py_credits as pyc
            on e.studentid = pyc.studentid
            and {{ union_dataset_join_clause(left_alias="e", right_alias="pyc") }}
        left join
            cy_credits as cyc
            on e.studentid = cyc.studentid
            and {{ union_dataset_join_clause(left_alias="e", right_alias="cyc") }}
        where
            e.enroll_status = 0
            and e.grade_level >= 9
            and e.academic_year = {{ var("current_academic_year") }}
    ),

    calcs as (
        select
            *,

            case
                when not is_age_eligible
                then 'Ineligible - Age'
                when is_first_time_ninth
                then 'Eligible'
                when not met_py_credits
                then 'Ineligble - Credits'
                when met_py_credits and py_y1_gpa < 2.2
                then 'Ineligible - GPA'
                when py_y1_ada >= 0.9 and py_y1_gpa >= 2.5 and met_py_credits
                then 'Eligible'
                when
                    py_y1_ada >= 0.9
                    and (py_y1_gpa >= 2.2 and py_y1_gpa <= 2.49)
                    and met_py_credits
                then 'Probation - GPA'
                when py_y1_ada < 0.9 and py_y1_gpa >= 2.5 and met_py_credits
                then 'Probation - ADA'
                when
                    py_y1_ada < 0.9
                    and (py_y1_gpa >= 2.2 and py_y1_gpa <= 2.49)
                    and met_py_credits
                then 'Probation - ADA and GPA'
            end as q1_eligibility,

            case
                when not is_age_eligible
                then 'Ineligible - Age'
                when not met_py_credits and not is_first_time_ninth
                then 'Ineligble - Credits'
                when (met_py_credits or is_first_time_ninth) and cy_q1_gpa < 2.2
                then 'Ineligible - GPA'
                when
                    cy_q1_ada >= 0.9
                    and cy_q1_gpa >= 2.5
                    and (met_py_credits or is_first_time_ninth)
                then 'Eligible'
                when
                    cy_q1_ada >= 0.9
                    and (cy_q1_gpa >= 2.2 and cy_q1_gpa <= 2.49)
                    and (met_py_credits or is_first_time_ninth)
                then 'Probation - GPA'
                when
                    cy_q1_ada < 0.9
                    and cy_q1_gpa >= 2.5
                    and (met_py_credits or is_first_time_ninth)
                then 'Probation - ADA'
                when
                    cy_q1_ada < 0.9
                    and (cy_q1_gpa >= 2.2 and cy_q1_gpa <= 2.49)
                    and (met_py_credits or is_first_time_ninth)
                then 'Probation - ADA and GPA'
            end as q2_eligibility,

            case
                when not is_age_eligible
                then 'Ineligible - Age'
                when not met_cy_credits
                then 'Ineligble - Credits'
                when met_cy_credits and cy_s1_gpa < 2.2
                then 'Ineligible - GPA'
                when cy_s1_ada >= 0.9 and cy_s1_gpa >= 2.5 and met_cy_credits
                then 'Eligible'
                when
                    cy_s1_ada >= 0.9
                    and (cy_s1_gpa >= 2.2 and cy_s1_gpa <= 2.49)
                    and met_cy_credits
                then 'Probation - GPA'
                when cy_s1_ada < 0.9 and cy_s1_gpa >= 2.5 and met_cy_credits
                then 'Probation - ADA'
                when
                    cy_s1_ada < 0.9
                    and (cy_s1_gpa >= 2.2 and cy_s1_gpa <= 2.49)
                    and met_cy_credits
                then 'Probation - ADA and GPA'
            end as q3_eligibility,

            case
                when not is_age_eligible
                then 'Ineligible - Age'
                when not met_cy_credits
                then 'Ineligble - Credits'
                when met_cy_credits and cy_s1_gpa < 2.2
                then 'Ineligible - GPA'
                when cy_s1_ada >= 0.9 and cy_s1_gpa >= 2.5 and met_cy_credits
                then 'Eligible'
                when
                    cy_s1_ada >= 0.9
                    and (cy_s1_gpa >= 2.2 and cy_s1_gpa <= 2.49)
                    and met_cy_credits
                then 'Probation - GPA'
                when cy_s1_ada < 0.9 and cy_s1_gpa >= 2.5 and met_cy_credits
                then 'Probation - ADA'
                when
                    cy_s1_ada < 0.9
                    and (cy_s1_gpa >= 2.2 and cy_s1_gpa <= 2.49)
                    and met_cy_credits
                then 'Probation - ADA and GPA'
            end as q4_eligibility,

        from base
    )

select
    u._dbt_source_relation,
    u.academic_year,
    u.yearid,
    u.student_number,
    u.students_dcid,
    u.studentid,
    u.grade_level,
    u.grade_level_prev,
    u.dob,
    u.is_age_eligible,
    u.is_first_time_ninth,

    u.cy_q1_ada,
    u.cy_s1_ada,
    u.py_y1_ada,
    u.cy_q1_gpa,
    u.cy_s1_gpa,
    u.py_y1_gpa,
    u.met_py_credits,
    u.met_cy_credits,

    t.is_current_term,

    quarter,
    eligibility,

    case
        when quarter = 'Q1' then 'Fall' when quarter = 'Q2' then 'Winter' else 'Spring'
    end as season,

from
    calcs unpivot (
        eligibility for quarter in (
            q1_eligibility as 'Q1',
            q2_eligibility as 'Q2',
            q3_eligibility as 'Q3',
            q4_eligibility as 'Q4'
        )
    ) as u
    
inner join
    term as t
    on u.yearid = t.yearid
    and u.schoolid = t.schoolid
    and u.quarter = t.term
    and {{ union_dataset_join_clause(left_alias="u", right_alias="t") }}

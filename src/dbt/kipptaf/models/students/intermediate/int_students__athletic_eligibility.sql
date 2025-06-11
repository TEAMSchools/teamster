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

            sum(if(y1_letter_grade_adjusted in ('F', 'F*'), 1, 0)) as n_failing,

        from {{ ref("base_powerschool__final_grades") }}
        where storecode = 'Q2'
        group by _dbt_source_relation, yearid, studentid
    ),

    base as (
        select
            e._dbt_source_relation,
            e.academic_year,
            e.yearid,
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

            if(cyc.n_failing = 0, true, false) as met_cy_credits,

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
                when is_first_time_ninth and cy_q1_ada >= 0.9
                then 'Eligible'
                when not met_py_credits and not is_first_time_ninth
                then 'Ineligble - Credits'
                when met_py_credits and cy_q1_gpa < 2.2
                then 'Ineligible - GPA'
                when cy_q1_ada >= 0.9 and cy_q1_gpa >= 2.5 and met_py_credits
                then 'Eligible'
                when
                    cy_q1_ada >= 0.9
                    and (cy_q1_gpa >= 2.2 and cy_q1_gpa <= 2.49)
                    and met_py_credits
                then 'Probation - GPA'
                when cy_q1_ada < 0.9 and cy_q1_gpa >= 2.5 and met_py_credits
                then 'Probation - ADA'
                when
                    cy_q1_ada < 0.9
                    and (cy_q1_gpa >= 2.2 and cy_q1_gpa <= 2.49)
                    and met_py_credits
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
    _dbt_source_relation,
    academic_year,
    yearid,
    student_number,
    students_dcid,
    studentid,
    grade_level,
    grade_level_prev,
    dob,
    is_age_eligible,
    is_first_time_ninth,

    cy_q1_ada,
    cy_s1_ada,
    py_y1_ada,
    cy_q1_gpa,
    cy_s1_gpa,
    py_y1_gpa,
    met_py_credits,
    met_cy_credits,

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
    )

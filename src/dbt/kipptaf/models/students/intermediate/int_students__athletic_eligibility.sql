with
    credits as (
        select
            _dbt_source_relation,
            studentsdcid,
            studentid,
            academic_year,
            cc_dcid,
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
            ) as py_earned_credits,

            avg(
                case when is_current_academic_year then academic_year_credits_earned end
            ) as cy_earned_credits,

            avg(
                case
                    when is_current_academic_year then academic_year_credits_potential
                end
            ) as cy_potential_credits,

        from yearly_credits
        group by _dbt_source_relation, studentsdcid
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

            a.ada_term as cy_q1_ada,
            a.ada_semester as cy_s1_ada,

            apy.ada_year as py_y1_ada,

            gq1.gpa_term as cy_q1_gpa,

            gs1.gpa_y1 as cy_s1_gpa,

            gp.gpa_y1 as py_y1_gpa,

            c.py_earned_credits,

            if(
                e.grade_level = 9
                and (e.grade_level_prev <= 8 or e.grade_level_prev is null),
                true,
                false
            ) as is_first_time_ninth,

            safe_divide(
                c.cy_earned_credits, cy_potential_credits
            ) as cy_credits_percent_passed,

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
            custom_yearly_credits as c
            on e.students_dcid = c.studentsdcid
            and {{ union_dataset_join_clause(left_alias="e", right_alias="c") }}
        where
            e.enroll_status = 0
            and e.grade_level >= 9
            and e.academic_year = {{ var("current_academic_year") }}
    ),

    calcs as (
        select
            *,

            case
                when is_first_time_ninth
                then 'Eligible'
                when py_earned_credits < 30
                then 'Ineligble - Credits'
                when py_earned_credits >= 30 and py_y1_gpa < 2.2
                then 'Ineligible - GPA'
                when py_y1_ada >= 0.9 and py_y1_gpa >= 2.5 and py_earned_credits >= 30
                then 'Eligible'
                when
                    py_y1_ada >= 0.9
                    and (py_y1_gpa >= 2.2 and py_y1_gpa <= 2.49)
                    and py_earned_credits >= 30
                then 'Probation - GPA'
                when py_y1_ada < 0.9 and py_y1_gpa >= 2.5 and py_earned_credits >= 30
                then 'Probation - ADA'
                when
                    py_y1_ada < 0.9
                    and (py_y1_gpa >= 2.2 and py_y1_gpa <= 2.49)
                    and py_earned_credits >= 30
                then 'Probation - ADA and GPA'
            end as q1_eligibility,

            case
                when is_first_time_ninth and cy_q1_ada >= 0.9
                then 'Eligible'
                when py_earned_credits < 30
                then 'Ineligble - Credits'
                when py_earned_credits >= 30 and py_y1_gpa < 2.2
                then 'Ineligible - GPA'
                when cy_q1_ada >= 0.9 and cy_q1_gpa >= 2.5 and py_earned_credits >= 30
                then 'Eligible'
                when
                    cy_q1_ada >= 0.9
                    and (cy_q1_gpa >= 2.2 and cy_q1_gpa <= 2.49)
                    and py_earned_credits >= 30
                then 'Probation - GPA'
                when cy_q1_ada < 0.9 and cy_q1_gpa >= 2.5 and py_earned_credits >= 30
                then 'Probation - ADA'
                when
                    cy_q1_ada < 0.9
                    and (cy_q1_gpa >= 2.2 and cy_q1_gpa <= 2.49)
                    and py_earned_credits >= 30
                then 'Probation - ADA and GPA'
            end as q2_eligibility,

            case
                when cy_credits_percent_passed < 1
                then 'Ineligble - Credits'
                when cy_credits_percent_passed = 1 and cy_s1_gpa < 2.2
                then 'Ineligible - GPA'
                when
                    cy_s1_ada >= 0.9
                    and cy_s1_gpa >= 2.5
                    and cy_credits_percent_passed = 1
                then 'Eligible'
                when
                    cy_s1_ada >= 0.9
                    and (cy_s1_gpa >= 2.2 and cy_s1_gpa <= 2.49)
                    and cy_credits_percent_passed = 1
                then 'Probation - GPA'
                when
                    cy_s1_ada < 0.9
                    and cy_s1_gpa >= 2.5
                    and cy_credits_percent_passed = 1
                then 'Probation - ADA'
                when
                    cy_s1_ada < 0.9
                    and (cy_s1_gpa >= 2.2 and cy_s1_gpa <= 2.49)
                    and cy_credits_percent_passed = 1
                then 'Probation - ADA and GPA'
            end as q3_eligibility,

            case
                when cy_credits_percent_passed < 1
                then 'Ineligble - Credits'
                when cy_credits_percent_passed = 1 and cy_s1_gpa < 2.2
                then 'Ineligible - GPA'
                when
                    cy_s1_ada >= 0.9
                    and cy_s1_gpa >= 2.5
                    and cy_credits_percent_passed = 1
                then 'Eligible'
                when
                    cy_s1_ada >= 0.9
                    and (cy_s1_gpa >= 2.2 and cy_s1_gpa <= 2.49)
                    and cy_credits_percent_passed = 1
                then 'Probation - GPA'
                when
                    cy_s1_ada < 0.9
                    and cy_s1_gpa >= 2.5
                    and cy_credits_percent_passed = 1
                then 'Probation - ADA'
                when
                    cy_s1_ada < 0.9
                    and (cy_s1_gpa >= 2.2 and cy_s1_gpa <= 2.49)
                    and cy_credits_percent_passed = 1
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
    is_first_time_ninth,

    cy_q1_ada,
    cy_s1_ada,
    py_y1_ada,
    cy_q1_gpa,
    cy_s1_gpa,
    py_y1_gpa,
    py_earned_credits,
    cy_credits_percent_passed,

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

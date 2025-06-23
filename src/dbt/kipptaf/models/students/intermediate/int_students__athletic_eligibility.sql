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
            e.ada_term_q1 as cy_q1_ada,
            e.ada_semester_s1 as cy_s1_ada,
            e.ada_year_prev as py_y1_ada,
            e.gpa_term_q1 as cy_q1_gpa,
            e.gpa_semester_s1 as cy_s1_gpa,
            e.gpa_year_prev as py_y1_gpa,

            pyc.met_py_credits,

            cyc.met_cy_credits,

            if(
                e.grade_level = 9
                and (e.grade_level_prev < 9 or e.grade_level_prev is null),
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
            py_credits as pyc
            on e.studentid = pyc.studentid
            and {{ union_dataset_join_clause(left_alias="e", right_alias="pyc") }}
        left join
            cy_credits as cyc
            on e.studentid = cyc.studentid
            and {{ union_dataset_join_clause(left_alias="e", right_alias="cyc") }}
        where
            e.academic_year = {{ var("current_academic_year") }}
            and e.enroll_status = 0
            and e.grade_level >= 9
    )

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

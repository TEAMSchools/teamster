with
    py_credits as (
        select
            _dbt_source_relation,
            yearid,
            studentid,

            {{ extract_source_project() }} as _dbt_source_project,

            sum(earnedcrhrs) as py_credits,

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

            {{ extract_source_project() }} as _dbt_source_project,

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
            e.`ada`,
            e.ada_unweighted_term_q1 as cy_unweighted_term_q1,
            e.ada_weighted_term_q1 as cy_weighted_term_q1,
            e.ada_unweighted_semester_s1 as cy_unweighted_s1_ada,
            e.ada_weighted_semester_s1 as cy_weighted_s1_ada,
            e.ada_unweighted_year_prev as py_y1_unweighted_ada,
            e.ada_weighted_year_prev as py_y1_weighted_ada,

            gpa.gpa_term_q1 as cy_q1_gpa,
            gpa.gpa_y1_q2 as cy_s1_gpa,
            gpa.gpa_y1_cur as cy_y1_gpa,

            gpapy.gpa_y1_cur as py_y1_gpa,

            pyc.py_credits,
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
                > 19,
                false,
                true
            ) as is_age_eligible,

        from {{ ref("int_extracts__student_enrollments") }} as e
        left join
            {{ ref("int_powerschool__gpa_term_pivot") }} as gpa
            on e.studentid = gpa.studentid
            and e.yearid = gpa.yearid
            and e._dbt_source_project = gpa._dbt_source_project
        left join
            {{ ref("int_powerschool__gpa_term_pivot") }} as gpapy
            on e.studentid = gpapy.studentid
            and e.yearid = (gpapy.yearid + 1)
            and e._dbt_source_project = gpapy._dbt_source_project
        left join
            py_credits as pyc
            on e.studentid = pyc.studentid
            and e._dbt_source_project = pyc._dbt_source_project
        left join
            cy_credits as cyc
            on e.studentid = cyc.studentid
            and e._dbt_source_project = cyc._dbt_source_project
        where
            e.academic_year = {{ var("current_academic_year") }}
            and e.rn_year = 1
            and e.enroll_status = 0
            and e.grade_level >= 5
            and e.region not in ('Paterson', 'Miami')
    )

select
    _dbt_source_relation,
    academic_year,
    yearid,
    schoolid,
    student_number,
    students_dcid,
    studentid,
    grade_level,
    grade_level_prev,
    dob,
    `ada`,
    cy_unweighted_term_q1,
    cy_weighted_term_q1,
    cy_unweighted_s1_ada,
    cy_weighted_s1_ada,
    py_y1_unweighted_ada,
    py_y1_weighted_ada,
    cy_q1_gpa,
    cy_s1_gpa,
    cy_y1_gpa,
    py_y1_gpa,
    py_credits,
    met_py_credits,
    met_cy_credits,
    is_first_time_ninth,
    is_age_eligible,

    {{ extract_source_project() }} as _dbt_source_project,

    case
        when not is_age_eligible
        then 'Ineligible - Age'
        when is_first_time_ninth or grade_level = 5
        then 'Eligible'
        when grade_level >= 9 and not met_py_credits
        then 'Ineligible - Credits'
        when grade_level >= 9 and met_py_credits and py_y1_gpa < 2.2
        then 'Ineligible - GPA'
        when grade_level <= 8 and py_y1_gpa < 2.2
        then 'Ineligible - GPA'
        when
            grade_level >= 9
            and met_py_credits
            and py_y1_unweighted_ada >= 0.9
            and py_y1_gpa >= 2.5
        then 'Eligible'
        when grade_level >= 6 and py_y1_unweighted_ada >= 0.9 and py_y1_gpa >= 2.5
        then 'Eligible'
        when
            grade_level >= 9
            and met_py_credits
            and py_y1_unweighted_ada >= 0.9
            and py_y1_gpa between 2.2 and 2.49
        then 'Probation - GPA'
        when
            grade_level >= 6
            and py_y1_unweighted_ada >= 0.9
            and py_y1_gpa between 2.2 and 2.49
        then 'Probation - GPA'
        when
            grade_level >= 9
            and met_py_credits
            and py_y1_unweighted_ada < 0.9
            and py_y1_gpa >= 2.5
        then 'Probation - ADA'
        when grade_level >= 6 and py_y1_unweighted_ada < 0.9 and py_y1_gpa >= 2.5
        then 'Probation - ADA'
        when
            grade_level >= 9
            and met_py_credits
            and py_y1_unweighted_ada < 0.9
            and py_y1_gpa between 2.2 and 2.49
        then 'Probation - ADA and GPA'
        when
            grade_level >= 6
            and py_y1_unweighted_ada < 0.9
            and py_y1_gpa between 2.2 and 2.49
        then 'Probation - ADA and GPA'
    end as q1_ae_status,

    case
        when not is_age_eligible
        then 'Ineligible - Age'
        when grade_level >= 9 and not met_py_credits and not is_first_time_ninth
        then 'Ineligible - Credits'
        when
            cy_q1_gpa < 2.2
            and (met_py_credits or is_first_time_ninth or grade_level >= 5)
        then 'Ineligible - GPA'
        when
            grade_level >= 9
            and cy_weighted_term_q1 >= 0.9
            and cy_q1_gpa >= 2.5
            and (met_py_credits or is_first_time_ninth)
        then 'Eligible'
        when grade_level >= 5 and `ada` >= 0.9 and cy_y1_gpa >= 2.5
        then 'Eligible'
        when
            grade_level >= 9
            and cy_weighted_term_q1 >= 0.9
            and cy_q1_gpa between 2.2 and 2.49
            and (met_py_credits or is_first_time_ninth)
        then 'Probation - GPA'
        when grade_level >= 5 and `ada` >= 0.9 and cy_y1_gpa between 2.2 and 2.49
        then 'Probation - GPA'
        when
            grade_level >= 9
            and cy_weighted_term_q1 < 0.9
            and cy_q1_gpa >= 2.5
            and (met_py_credits or is_first_time_ninth)
        then 'Probation - ADA'
        when grade_level >= 5 and `ada` < 0.9 and cy_y1_gpa >= 2.5
        then 'Probation - ADA'
        when
            grade_level >= 9
            and cy_weighted_term_q1 < 0.9
            and cy_q1_gpa between 2.2 and 2.49
            and (met_py_credits or is_first_time_ninth)
        then 'Probation - ADA and GPA'
    end as q2_ae_status,

    case
        when not is_age_eligible
        then 'Ineligible - Age'
        when grade_level >= 9 and not met_cy_credits
        then 'Ineligible - Credits'
        when grade_level >= 9 and met_cy_credits and cy_s1_gpa < 2.2
        then 'Ineligible - GPA'
        when grade_level >= 5 and cy_y1_gpa < 2.2
        then 'Ineligible - GPA'
        when
            grade_level >= 9
            and met_cy_credits
            and cy_weighted_s1_ada >= 0.9
            and cy_s1_gpa >= 2.5
        then 'Eligible'
        when grade_level >= 5 and `ada` >= 0.9 and cy_y1_gpa >= 2.5
        then 'Eligible'
        when
            grade_level >= 9
            and met_cy_credits
            and cy_weighted_s1_ada >= 0.9
            and cy_s1_gpa between 2.2 and 2.49
        then 'Probation - GPA'
        when grade_level >= 5 and `ada` >= 0.9 and cy_y1_gpa between 2.2 and 2.49
        then 'Probation - GPA'
        when
            grade_level >= 9
            and met_cy_credits
            and cy_weighted_s1_ada < 0.9
            and cy_s1_gpa >= 2.5
        then 'Probation - ADA'
        when grade_level >= 5 and `ada` < 0.9 and cy_y1_gpa >= 2.5
        then 'Probation - ADA'
        when
            grade_level >= 9
            and met_cy_credits
            and cy_weighted_s1_ada < 0.9
            and cy_s1_gpa between 2.2 and 2.49
        then 'Probation - ADA and GPA'
    end as q3_ae_status,

    case
        when not is_age_eligible
        then 'Ineligible - Age'
        when grade_level >= 9 and not met_cy_credits
        then 'Ineligible - Credits'
        when grade_level >= 9 and met_cy_credits and cy_s1_gpa < 2.2
        then 'Ineligible - GPA'
        when grade_level >= 5 and cy_y1_gpa < 2.2
        then 'Ineligible - GPA'
        when
            grade_level >= 9
            and met_cy_credits
            and cy_weighted_s1_ada >= 0.9
            and cy_s1_gpa >= 2.5
        then 'Eligible'
        when grade_level >= 5 and `ada` >= 0.9 and cy_y1_gpa >= 2.5
        then 'Eligible'
        when
            grade_level >= 9
            and met_cy_credits
            and cy_weighted_s1_ada >= 0.9
            and cy_s1_gpa between 2.2 and 2.49
        then 'Probation - GPA'
        when grade_level >= 5 and `ada` >= 0.9 and cy_y1_gpa between 2.2 and 2.49
        then 'Probation - GPA'
        when
            grade_level >= 9
            and met_cy_credits
            and cy_weighted_s1_ada < 0.9
            and cy_s1_gpa >= 2.5
        then 'Probation - ADA'
        when grade_level >= 5 and `ada` < 0.9 and cy_y1_gpa >= 2.5
        then 'Probation - ADA'
        when
            grade_level >= 9
            and met_cy_credits
            and cy_weighted_s1_ada < 0.9
            and cy_s1_gpa between 2.2 and 2.49
        then 'Probation - ADA and GPA'
    end as q4_ae_status,

from base

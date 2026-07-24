with
    grade_source as (
        select
            'Stored' as gpa_type,

            co.school_abbreviation,
            co.grade_level,
            co.student_number,
            co.lastfirst,

            sg.course_number,
            sg.agg_credittype as credittype,
            sg.potentialcrhrs,

            sg.earnedcrhrs,
            sg.gpa_points,

        from {{ ref("stg_powerschool__storedgrades") }} as sg
        inner join
            {{ ref("base_powerschool__student_enrollments") }} as co
            on sg.studentid = co.studentid
            and sg._dbt_source_project = co._dbt_source_project
            and sg.schoolid = co.schoolid
            and co.grade_level >= 9
            and co.rn_year = 1
            and co.enroll_status = 0
            and co.academic_year = {{ var("current_academic_year") }}
        where sg.storecode = 'Y1'

        union all

        select
            'Live' as gpa_type,

            co.school_abbreviation,
            co.grade_level,
            co.student_number,
            co.lastfirst,

            fg.course_number,
            fg.credittype,
            fg.courses_credit_hours as potentialcrhrs,

            if(
                fg.y1_letter_grade_adjusted not like 'F%', fg.courses_credit_hours, 0
            ) as earnedcrhrs,

            if(
                fg.y1_letter_grade_adjusted not like 'F%', fg.y1_grade_points, 0
            ) as gpa_points,

        from {{ ref("base_powerschool__final_grades") }} as fg
        inner join
            {{ ref("base_powerschool__student_enrollments") }} as co
            on fg.studentid = co.studentid
            and fg._dbt_source_project = co._dbt_source_project
            and fg.schoolid = co.schoolid
            and fg.academic_year = co.academic_year
            and co.grade_level >= 9
            and co.rn_year = 1
            and co.enroll_status = 0
        where
            co.academic_year = {{ var("current_academic_year") }}
            and fg.storecode = 'Q4'
    ),

    calculations as (
        select
            school_abbreviation,
            grade_level,
            student_number,
            lastfirst,
            credittype,

            round(
                sum(gpa_points * earnedcrhrs) / sum(potentialcrhrs), 3
            ) as gpa_subject,

        from grade_source
        where
            potentialcrhrs != 0
            and credittype in ('ENG', 'MATH', 'SCI', 'SOC', 'WLANG', 'ART', 'PHYSED')
        group by school_abbreviation, grade_level, student_number, lastfirst, credittype
    )

select
    school_abbreviation as school,
    grade_level,
    student_number,
    lastfirst as student_name,
    eng as english,
    math,
    sci as science,
    soc as social_studies,
    wlang as world_language,
    art as vpa,
    physed,

from
    calculations pivot (
        max(gpa_subject) for credittype
        in ('ENG', 'MATH', 'SCI', 'SOC', 'WLANG', 'ART', 'PHYSED')
    )

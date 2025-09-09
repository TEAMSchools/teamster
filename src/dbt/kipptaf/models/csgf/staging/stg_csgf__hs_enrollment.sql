with
    course_tags as (
        select
            _dbt_source_relation,
            cc_studentid,

            if(
                sum(if(is_ap_course, 1, 0)) = 0, 'N', 'Y'
            ) as has_participated_in_ap_courses,

            if(
                sum(if(courses_course_name like '%Honors%', 1, 0)) = 0, 'N', 'Y'
            ) as has_participated_in_honors_courses,

            if(
                sum(if(courses_course_name like '%(DE)', 1, 0)) = 0, 'N', 'Y'
            ) as has_participated_in_dual_enrollment_courses,

            if(
                sum(if(cte_college_credits is null, 0, 1)) = 0, 'N', 'Y'
            ) as has_participated_in_cte_courses,

        from {{ ref("base_powerschool__course_enrollments") }}
        where
            students_grade_level >= 9
            and rn_credittype_year = 1
            and rn_course_number_year = 1
            and not is_dropped_course
            and cc_academic_year < {{ var("current_academic_year") }}
        group by _dbt_source_relation, cc_studentid
    ),

    passed_courses as (
        select
            c._dbt_source_relation,
            c.cc_studentid,

            e.grade_level,

            max(if(g.grade like 'F%', 0, 1)) over (
                partition by student_number
            ) as passed_algebra_i,

            row_number() over (
                partition by e.student_number order by e.grade_level
            ) as rn,

        from {{ ref("base_powerschool__course_enrollments") }} as c
        inner join
            {{ ref("int_extracts__student_enrollments") }} as e
            on c.cc_academic_year = e.academic_year
            and c.cc_studentid = e.studentid
            and {{ union_dataset_join_clause(left_alias="c", right_alias="e") }}
        inner join
            {{ ref("stg_powerschool__storedgrades") }} as g
            on c.cc_academic_year = g.academic_year
            and c.sections_id = g.sectionid
            and c.cc_studentid = g.studentid
            and {{ union_dataset_join_clause(left_alias="c", right_alias="g") }}
            and g.storecode = 'Y1'
        left join
            {{ ref("stg_crdc__sced_code_crosswalk") }} as x
            on concat(c.nces_subject_area, c.nces_course_id) = x.sced_code
        where
            c.cc_academic_year < {{ var("current_academic_year") }}
            and c.rn_credittype_year = 1
            and c.rn_course_number_year = 1
            and not c.is_dropped_course
            and x.sced_course_name in (
                'Integrated Mathematics I',
                'Algebra I',
                'Algebra I – Part 1',
                'Algebra I – Part 2'
            )
            or c.courses_course_name = 'Math I Algebra'
    )

select
    e.student_number as studentid,
    e.grade_level as grade,

    g.cumulative_y1_gpa_unweighted as unweighted_cumulative_gpa,
    g.cumulative_y1_gpa as weighted_cumulative_gpa,

    c.has_participated_in_ap_courses,
    c.has_participated_in_honors_courses,
    c.has_participated_in_dual_enrollment_courses,
    c.has_participated_in_cte_courses,

    'NA' as has_participated_in_ib_courses,
    'NA (not offered)' as passed_integrated_math_1,

    case
        e.school_name
        when 'KIPP Cooper Norcross High'
        then 'KIPP Cooper Norcross High School'
        else e.school_name
    end as school,

    case
        e.ethnicity
        when 'I'
        then 'American Indian or Alaska Native'
        when 'A'
        then 'Asian'
        when 'B'
        then 'Black or African American'
        when 'H'
        then 'Hispanic or Latino of any race'
        when 'P'
        then 'Native Hawaiian or Other Pacific Islander'
        when 'W'
        then 'White'
        when 'T'
        then 'Two or more races'
        else 'Did Not State'
    end as race_ethnicity,

    case
        e.gender
        when 'F'
        then 'Female'
        when 'M'
        then 'Male'
        when 'X'
        then 'Nonbinary/Nonconforming'
        else 'Did Not State'
    end as gender,

    if(e.iep_status = 'Has IEP', 'Y', 'N') as student_has_iep,

    if(e.lep_status, 'Y', 'N') as student_is_el,

    if(e.lunch_status in ('F', 'R'), 'Y', 'N') as student_is_frl,

from {{ ref("int_extracts__student_enrollments") }} as e
left join
    {{ ref("int_powerschool__gpa_cumulative") }} as g
    on e.studentid = g.studentid
    and {{ union_dataset_join_clause(left_alias="e", right_alias="g") }}
left join
    course_tags as c
    on e.studentid = c.cc_studentid
    and {{ union_dataset_join_clause(left_alias="e", right_alias="c") }}
where
    e.academic_year = {{ var("current_academic_year") - 1 }}
    and e.school_level = 'HS'
    and e.enroll_status in (0, 3)
    and e.rn_year = 1

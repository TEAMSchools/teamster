with
    earned_course_grades as (
        select
            sg._dbt_source_project,
            sg.studentid,
            sg.schoolid,

            if(cx.ap_course_subject is not null, 1, 0) as is_ap_course,

            if(c.course_name like '%Honors%', 1, 0) as is_honors_course,

            if(c.course_name like '%(DE)', 1, 0) as is_dual_course,

            if(cx.ctecollegecredits is not null, 1, 0) as is_cte_course,
        from {{ ref("stg_powerschool__storedgrades") }} as sg
        left join
            {{ ref("stg_powerschool__courses") }} as c
            on sg.course_number = c.course_number
            and sg._dbt_source_project = c._dbt_source_project
        left join
            {{ ref("stg_powerschool__s_nj_crs_x") }} as cx
            on c.dcid = cx.coursesdcid
            and c._dbt_source_project = cx._dbt_source_project
        where
            sg.storecode = 'Y1'
            and not sg.is_transfer_grade
            and sg.grade_level >= 9
            and sg.academic_year < {{ var("current_academic_year") }}
    ),

    course_tags as (
        select
            _dbt_source_project,
            studentid,
            schoolid,

            if(sum(is_ap_course) = 0, 'N', 'Y') as has_participated_in_ap_courses,

            if(
                sum(is_honors_course) = 0, 'N', 'Y'
            ) as has_participated_in_honors_courses,

            if(
                sum(is_dual_course) = 0, 'N', 'Y'
            ) as has_participated_in_dual_enrollment_courses,

            if(sum(is_cte_course) = 0, 'N', 'Y') as has_participated_in_cte_courses,

        from earned_course_grades
        group by _dbt_source_project, studentid, schoolid
    )

select
    e.student_number as studentid,
    e.grade_level as grade,
    e.cumulative_y1_gpa_unweighted as unweighted_cumulative_gpa,
    e.cumulative_y1_gpa as weighted_cumulative_gpa,
    e.exited_hs,

    'NA' as has_participated_in_ib_courses,
    'NA (not offered)' as passed_integrated_math_1,

    /* a student with no Y1 grade at the school reads N, not blank */
    coalesce(c.has_participated_in_ap_courses, 'N') as has_participated_in_ap_courses,
    coalesce(
        c.has_participated_in_honors_courses, 'N'
    ) as has_participated_in_honors_courses,
    coalesce(
        c.has_participated_in_dual_enrollment_courses, 'N'
    ) as has_participated_in_dual_enrollment_courses,
    coalesce(c.has_participated_in_cte_courses, 'N') as has_participated_in_cte_courses,

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

    if(
        e.school_name = 'KIPP Cooper Norcross High',
        'KIPP Cooper Norcross High School',
        e.school_name
    ) as school,

    if(e.iep_status = 'Has IEP', 'Y', 'N') as student_has_iep,

    if(e.lep_status, 'Y', 'N') as student_is_el,

    if(e.lunch_status in ('F', 'R', 'FDC'), 'Y', 'N') as student_is_frl,

from {{ ref("int_extracts__student_enrollments") }} as e
left join
    course_tags as c
    on e.studentid = c.studentid
    and e._dbt_source_project = c._dbt_source_project
    and e.schoolid = c.schoolid
where
    e.academic_year = {{ var("current_academic_year") - 1 }}
    and e.school_level = 'HS'
    and e.rn_year = 1
    and e.is_enrolled_recent

with
    transfer_course_tags as (
        select
            studentid,
            grade_level,

            0 as is_dual_course,

            0 as is_cte_course,

            initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')) as region,

            if(grade like 'F%', 0, 1) as passed_class,

            if(
                course_name like '%Alg%'
                or course_name like '%ALG%'
                or course_name like '%Alb%'
                or course_name like 'Math%'
                or course_name = 'GSE Coord Alegbra'
                or course_name = 'NC Math 1',
                1,
                0
            ) as is_alg_i_course,

            if(course_name like 'AP%', 1, 0) as is_ap_course,

            if(course_name like '%Honors%', 1, 0) as is_honors_course,

        from {{ ref("stg_powerschool__storedgrades") }} as g
        where
            storecode = 'Y1'
            and is_transfer_grade
            and academic_year >= {{ var("current_academic_year") - 6 }}
            and course_name in (
                'Academic Algebra I',
                'Access Algebra I A',
                'Albegra 1',
                'ALG 1',
                'Alg I',
                'Alg 1'
                'ALG I CP',
                'Algebra',
                'Algebra 1',
                'ALGEBRA 1',
                'Algebra 1 (CR)',
                'Algebra 1 (for HS credit)',
                'Algebra 1 (SS)',
                'Algebra 1 C. P.',
                'Algebra 1 Concepts-Modify',
                'Algebra 1 CP',
                'Algebra 1 Honors (CR)',
                'Algebra 1 Honors (H)',
                'ALGEBRA I',
                'Algebra I ',
                'Algebra I',
                'Algebra I (CR)',
                'Algebra I (for HS credit)',
                'Algebra I (S)',
                'Algebra I Accelerated',
                'Algebra I Advanced',
                'Algebra I CC',
                'Algebra I College Prep Freshmen',
                'Algebra I HON',
                'Algebra I Honors',
                'Algebra I NG',
                'Algebra I PSP',
                'Algebra I Summer School (CR)',
                'Algebra I-CP',
                'Algebra I CP',
                'Algebra1',
                'Alglebra I',
                'AP Biology',
                'AP Biology I',
                'AP Biology I (CR)',
                'AP Chemistry',
                'AP Computer Science Principles',
                'AP Eng Lit',
                'AP Literature',
                'AP Modern World History',
                'AP Music Theory',
                'AP United States History',
                'AP World History',
                'AP World History I',
                'AP World History II',
                'AP World History: Modern',
                'AP World History: Modern (CR)',
                'AP: English Literature & Composition',
                'Honors Algebra 1',
                'Honors Algebra I',
                'Honors Algebra I (H)',
                'Honors Biology',
                'Honors Biology I',
                'Honors Biology with Lab',
                'Honors Biology Wth Lab',
                'Honors Chemistry',
                'Honors Earth/Environmental Science',
                'Honors Eng II (H)',
                'Honors English I',
                'Honors English II',
                'Honors Forensic Science',
                'Honors Geometry',
                'Honors Global Studies',
                'Honors Global Studies (H)',
                'Honors Integrated Science (Lab)',
                'Honors NC Math 2',
                'Honors Physics',
                'Honors Physics With Lab',
                'Honors Psychology',
                'Honors Spanish II',
                'Honors United States History I',
                'Honors United States History II',
                'Honors United States Histroy I',
                'Honors World History',
                'Intensive Algerba I',
                'Mathematics 9: Algebra I',
                'Mathematics-Algebra I',
                'MPD/Algebra I',
                'Mathematics 9',
                'Algebra 1A Applied CP',
                'Math 9',
                'Algebra I A',
                'Pre-AP Algebra I',
                'GSE Coord Alegbra',
                'Mathematics',
                'Int Algebra ACC',
                'Math',
                'NC Math 1',
                'MPD/Algebra I Lab',
                'Algebra I Foundations (CR)'
            )
    ),

    local_course_tags as (
        select
            cc_studentid as studentid,

            initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')) as region,

            if(is_ap_course, 1, 0) as is_ap_course,

            if(courses_course_name like '%Honors%', 1, 0) as is_honors_course,

            if(courses_course_name like '%(DE)', 1, 0) as is_dual_course,

            if(cte_college_credits is null, 0, 1) as is_cte_course,

        from {{ ref("base_powerschool__course_enrollments") }}
        where
            students_grade_level >= 9
            and rn_credittype_year = 1
            and rn_course_number_year = 1
            and not is_dropped_course
            and cc_academic_year < {{ var("current_academic_year") }}
    ),

    course_tags_union as (
        select
            region,
            studentid,

            is_ap_course,
            is_honors_course,
            is_dual_course,
            is_cte_course,

        from local_course_tags

        union all

        select
            region,
            studentid,

            is_ap_course,
            is_honors_course,
            is_dual_course,
            is_cte_course,

        from transfer_course_tags
    ),

    course_tags as (
        select
            region,
            studentid,

            if(sum(is_ap_course) = 0, 'N', 'Y') as has_participated_in_ap_courses,

            if(
                sum(is_honors_course) = 0, 'N', 'Y'
            ) as has_participated_in_honors_courses,

            if(
                sum(is_dual_course) = 0, 'N', 'Y'
            ) as has_participated_in_dual_enrollment_courses,

            if(sum(is_cte_course) = 0, 'N', 'Y') as has_participated_in_cte_courses,

        from course_tags_union
        group by region, studentid
    ),

    passed_courses_union as (
        select
            c.cc_studentid as studentid,
            e.grade_level,
            e.region,

            max(if(g.grade like 'F%', 0, 1)) over (
                partition by student_number
            ) as passed_algebra_i,

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
            {{ ref("stg_google_sheets__crdc__sced_code_crosswalk") }} as x
            on concat(c.nces_subject_area, c.nces_course_id) = x.sced_code
        where
            c.cc_academic_year < {{ var("current_academic_year") }}
            and c.rn_course_number_year = 1
            and not c.is_dropped_course
            and x.sced_course_name in (
                'Integrated Mathematics I',
                'Algebra I',
                'Algebra I – Part 1',
                'Algebra I – Part 2'
            )
            or c.courses_course_name = 'Math I Algebra'

        union all

        select
            studentid,
            grade_level,
            region,

            max(passed_class) over (partition by region, studentid) as passed_algebra_i,

        from transfer_course_tags
        where is_alg_i_course = 1
    ),

    passed_courses as (
        select
            region,
            studentid,
            grade_level,

            max(passed_algebra_i) over (
                partition by region, studentid
            ) as passed_algebra_i,

            row_number() over (
                partition by region, studentid order by grade_level
            ) as rn,

        from passed_courses_union
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

    case
        when p.passed_algebra_i = 0 or p.passed_algebra_i is null
        then 'Has not yet passed/never taken'
        when p.passed_algebra_i = 1 and p.grade_level <= 8
        then 'Passed Before 9th'
        when p.passed_algebra_i = 1 and p.grade_level = 9
        then 'Passed in 9th'
        when p.passed_algebra_i = 1 and p.grade_level = 10
        then 'Passed in 10th'
        when p.passed_algebra_i = 1 and p.grade_level = 11
        then 'Passed in 11th'
        when p.passed_algebra_i = 1 and p.grade_level = 12
        then 'Passed in 12th'
    end as passed_algebra_i,

    if(
        e.school_name = 'KIPP Cooper Norcross High',
        'KIPP Cooper Norcross High School',
        e.school_name
    ) as school,

    if(e.iep_status = 'Has IEP', 'Y', 'N') as student_has_iep,

    if(e.lep_status, 'Y', 'N') as student_is_el,

    if(e.lunch_status in ('F', 'R'), 'Y', 'N') as student_is_frl,

from {{ ref("int_extracts__student_enrollments") }} as e
left join
    {{ ref("int_powerschool__gpa_cumulative") }} as g
    on e.studentid = g.studentid
    and e.schoolid = g.schoolid
    and {{ union_dataset_join_clause(left_alias="e", right_alias="g") }}
left join course_tags as c on e.studentid = c.studentid and e.region = c.region
left join
    passed_courses as p
    on e.studentid = p.studentid
    and e.region = p.region
    and p.rn = 1
where
    e.academic_year = {{ var("current_academic_year") - 1 }}
    and e.school_level = 'HS'
    and e.enroll_status in (0, 3)
    and e.rn_year = 1
    and e.is_enrolled_recent

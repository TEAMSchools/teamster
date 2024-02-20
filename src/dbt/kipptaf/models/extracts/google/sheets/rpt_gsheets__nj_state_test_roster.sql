with
    courses as (
        select
            c.cc_academic_year as academic_year,
            c.students_student_number as student_number,
            c.courses_credittype as credittype,
            case
                when c.courses_credittype = 'MATH' and nj.nces_course_id = '052'
                then 'ALG01'
                when c.courses_credittype = 'MATH' and nj.nces_course_id = '072'
                then 'GEO01'
                when c.courses_credittype = 'MATH' and nj.nces_course_id = '056'
                then 'ALG02'
            end as math_course,
        from {{ ref("base_powerschool__course_enrollments") }} as c
        left join
            {{ ref("stg_powerschool__s_nj_crs_x") }} as nj
            on c.courses_dcid = nj.coursesdcid
            and {{ union_dataset_join_clause(left_alias="c", right_alias="nj") }}
        where c.rn_credittype_year = 1 and not c.is_dropped_section
    ),

    roster as (
        select
            co.academic_year,
            co.rn_year,
            co.region,
            co.is_self_contained,
            co.school_level,
            co.school_abbreviation,
            co.grade_level,
            co.advisory_name,
            co.student_number,
            co.state_studentnumber,
            co.lastfirst as student_name,
            co.special_education_code,

            subj as subject,

            if(co.enroll_status = 0, 'Enrolled', 'Transferred Out') as enroll_status,
            concat(co.lastfirst, ' - ', co.student_number, ' - ', subj) as student,
            case
                when subj = 'MATH' and nj.asmt_extended_time_math is not null
                then true
                when subj = 'ENG' and nj.asmt_extended_time is not null
                then true
                when subj = 'SCI' and nj.asmt_extended_time_math is not null
                then true
                else false
            end as has_extended_time,
            if(co.spedlep like 'SPED%', 'IEP', 'No IEP') as iep_status,
            if(co.lep_status, 'LEP', 'Not LEP') as lep_status,
            if(co.is_504, 'Has 504', 'No 504') as status_504,
            case
                when subj = 'MATH' and nj.graduation_pathway_math = 'M'
                then null
                when subj = 'MATH' and nj.math_state_assessment_name = '3'
                then null
                when subj = 'MATH' and co.grade_level = 11
                then 'MATGP'
                when subj = 'MATH' and co.school_level = 'HS' and c.math_course is null
                then 'NO MATH COURSE ASSIGNED'
                when
                    subj = 'MATH'
                    and co.school_level in ('MS', 'HS')
                    and c.math_course is not null
                then c.math_course
                when subj = 'MATH' and c.math_course is null
                then concat('MAT', '0', co.grade_level)
                when subj = 'ENG' and nj.graduation_pathway_ela = 'M'
                then null
                when subj = 'ENG' and nj.state_assessment_name in ('2', '3', '4')
                then null
                when subj = 'ENG' and co.grade_level = 11
                then 'ELAGP'
                when subj = 'ENG'
                then concat('ELA', '0', co.grade_level)
                when subj = 'SCI' and co.grade_level in (5, 8)
                then concat('SC', '0', co.grade_level)
                when subj = 'SCI' and co.grade_level = 11
                then 'SC11'
            end as test_code,
        from {{ ref("base_powerschool__student_enrollments") }} as co
        cross join unnest(['ENG', 'MATH', 'SCI']) as subj
        left join
            courses as c
            on co.academic_year = c.academic_year
            and co.student_number = c.student_number
            and subj = c.credittype
        left join
            {{ ref("stg_powerschool__s_nj_stu_x") }} as nj
            on co.students_dcid = nj.studentsdcid
            and {{ union_dataset_join_clause(left_alias="co", right_alias="nj") }}
    )

select
    region,
    school_abbreviation,
    student,
    enroll_status,
    grade_level,
    advisory_name,
    student_number,
    state_studentnumber,
    iep_status,
    lep_status,
    status_504,
    test_code,
    has_extended_time,
    concat(student_number, '_', test_code) as sn_test_hash,
from roster
where
    academic_year = 2023
    and rn_year = 1
    and region != 'Miami'
    and (grade_level between 3 and 9 or grade_level = 11)
    and not (is_self_contained and special_education_code in ('CMI', 'CMO', 'CSE'))
    and school_level != 'OD'
    and test_code is not null

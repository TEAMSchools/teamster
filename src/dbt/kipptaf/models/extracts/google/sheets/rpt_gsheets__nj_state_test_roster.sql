with
    courses as (
        select
            cc_academic_year as academic_year,
            students_student_number as student_number,
            courses_credittype as credittype,
            case
                when courses_credittype = 'MATH' and nces_course_id = '052'
                then 'ALG01'
                when courses_credittype = 'MATH' and nces_course_id = '072'
                then 'GEO01'
                when courses_credittype = 'MATH' and nces_course_id = '056'
                then 'ALG02'
            end as math_course,
        from {{ ref("base_powerschool__course_enrollments") }}
        where rn_credittype_year = 1 and not is_dropped_section
    ),

    roster_long as (
        select
            co.region,
            co.is_self_contained,
            co.school_level,
            co.school,
            co.grade_level,
            co.advisory_name,
            co.student_number,
            co.state_studentnumber,
            co.student_name,
            co.special_education_code,
            co.iep_status,
            co.enroll_status,
            co.lep_status,
            co.status_504,

            -- exemption source fields (preserved through pivot for reason labels)
            nj.math_state_assessment_name,
            nj.state_assessment_name,
            sub.ps_grad_path_code,
            sub.is_exempt_state_testing,

            subj as `subject`,

            -- display string is student-scoped, not test-scoped
            concat(co.student_name, ' - ', co.student_number) as student,

            case
                when subj = 'MATH' and nj.asmt_extended_time_math is not null
                then true
                when subj = 'ENG' and nj.asmt_extended_time is not null
                then true
                when subj = 'SCI' and nj.asmt_extended_time_math is not null
                then true
                else false
            end as has_extended_time,

            case
                when subj = 'MATH' and sub.ps_grad_path_code = 'M'
                then null
                when subj = 'MATH' and sub.is_exempt_state_testing
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
                when subj = 'ENG' and sub.ps_grad_path_code = 'M'
                then null
                when subj = 'ENG' and sub.is_exempt_state_testing
                then null
                when subj = 'ENG' and co.grade_level = 11
                then 'ELAGP'
                when subj = 'ENG'
                then concat('ELA', '0', co.grade_level)
                when
                    subj = 'SCI'
                    and co.grade_level in (5, 8, 11)
                    and nj.math_state_assessment_name = '3'
                then null
                when subj = 'SCI' and co.grade_level in (5, 8)
                then concat('SC', '0', co.grade_level)
                when subj = 'SCI' and co.grade_level = 11
                then 'SC11'
            end as test_code,
        from {{ ref("int_extracts__student_enrollments") }} as co
        cross join unnest(['ENG', 'MATH', 'SCI']) as subj
        left join
            courses as c
            on co.academic_year = c.academic_year
            and co.student_number = c.student_number
            and subj = c.credittype
        left join
            {{ ref("int_extracts__student_enrollments_subjects") }} as sub
            on co.student_number = sub.student_number
            and co.academic_year = sub.academic_year
            and subj = sub.powerschool_credittype
            and sub.rn_year = 1
        left join
            {{ ref("stg_powerschool__s_nj_stu_x") }} as nj
            on co.students_dcid = nj.studentsdcid
            and {{ union_dataset_join_clause(left_alias="co", right_alias="nj") }}
        where
            co.academic_year = {{ var("current_academic_year") }}
            and co.rn_year = 1
            and (co.grade_level between 3 and 9 or co.grade_level = 11)
            and co.region != 'Miami'
            and co.school_level != 'OD'
    ),

    roster as (
        select
            student_number,
            any_value(region) as region,
            any_value(school) as school,
            any_value(student) as student,
            any_value(enroll_status) as enroll_status,
            any_value(grade_level) as grade_level,
            any_value(advisory_name) as advisory_name,
            any_value(state_studentnumber) as state_studentnumber,
            any_value(iep_status) as iep_status,
            any_value(lep_status) as lep_status,
            any_value(status_504) as status_504,
            any_value(special_education_code) as special_education_code,
            any_value(is_self_contained) as is_self_contained,

            -- exemption source fields
            any_value(math_state_assessment_name) as math_state_assessment_name,
            any_value(state_assessment_name) as state_assessment_name,
            max(
                case when `subject` = 'ENG' then ps_grad_path_code end
            ) as ela_grad_path_code,
            max(
                case when `subject` = 'MATH' then ps_grad_path_code end
            ) as math_grad_path_code,

            -- per-subject test codes
            max(case when `subject` = 'ENG' then test_code end) as ela_test_code,
            max(case when `subject` = 'MATH' then test_code end) as math_test_code,
            max(case when `subject` = 'SCI' then test_code end) as sci_test_code,

            -- per-subject extended time
            max(
                case when `subject` = 'ENG' then has_extended_time end
            ) as ela_has_extended_time,
            max(
                case when `subject` = 'MATH' then has_extended_time end
            ) as math_has_extended_time,
            max(
                case when `subject` = 'SCI' then has_extended_time end
            ) as sci_has_extended_time,
        from roster_long
        group by student_number
    )

select
    region,
    school,
    student,
    enroll_status,
    grade_level,
    advisory_name,
    student_number,
    state_studentnumber,
    iep_status,
    lep_status,
    status_504,
    special_education_code,
    is_self_contained,

    ela_test_code,
    math_test_code,
    sci_test_code,

    ela_has_extended_time,
    math_has_extended_time,
    sci_has_extended_time,

    -- why is ELA exempt? (null = not exempt)
    case
        when ela_test_code is not null
        then null
        when ela_grad_path_code = 'M'
        then 'IEP - Graduation Pathway'
        when state_assessment_name = '4'
        then 'DLM + ACCESS (IEP and ML)'
        when state_assessment_name = '3'
        then 'DLM - Alternate Assessment'
        when state_assessment_name = '2'
        then 'ACCESS Only - ML Exempt'
        else 'ELA Exempt - Other'
    end as ela_exemption_reason,

    -- why is Math exempt? (null = not exempt)
    case
        when math_test_code is not null
        then null
        when math_grad_path_code = 'M'
        then 'IEP - Graduation Pathway'
        when math_state_assessment_name = '3'
        then 'DLM - Alternate Assessment'
        else 'Math Exempt - Other'
    end as math_exemption_reason,

    -- summary visual flag for quick stakeholder scan (null = no exemptions)
    case
        when ela_test_code is null and math_test_code is null
        then 'ELA and Math Exempt'
        when ela_test_code is null
        then 'ELA Exempt'
        when math_test_code is null
        then 'Math Exempt'
    end as subject_exemption_flag,

from roster
where
    ela_test_code is not null or math_test_code is not null or sci_test_code is not null

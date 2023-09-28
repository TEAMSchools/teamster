with
    roster as (
        select
            e.academic_year,
            e.region,
            e.schoolid,
            e.school_name,
            e.school_abbreviation,
            e.students_dcid,
            e.student_number,
            e.state_studentnumber,
            adb.contact_id,
            e.lastfirst,
            e.first_name,
            e.last_name,
            e.grade_level,
            e.student_email_google,
            e.cohort,
            e.enroll_status,
            e.spedlep as iepstatus,
            e.is_504 as c_504_status,
            e.is_retained_year,
            e.is_retained_ever,
            e.advisor_lastfirst as advisor_name,
            s.courses_course_name as ccr_course,
            s.teacher_lastfirst as ccr_teacher,
            s.sections_external_expression as ccr_period,
        from {{ ref("base_powerschool__student_enrollments") }} as e
        left join
            {{ ref("base_powerschool__course_enrollments") }} as s
            on e.academic_year = s.cc_academic_year
            and e.studentid = s.cc_studentid
            and {{ union_dataset_join_clause(left_alias="e", right_alias="s") }}
        left join
            {{ ref("int_kippadb__roster") }} as adb
            on e.student_number = adb.student_number
        where
            e.rn_year = 1
            and e.academic_year = {{ var("current_academic_year") }}
            and e.cohort between ({{ var("current_academic_year") }}- 1) and (
                {{ var("current_academic_year") }} + 5
            )
            and e.schoolid <> 999999
            and s.courses_course_name like 'College and Career%'
            and s.rn_course_number_year = 1
            and not s.is_dropped_section
            and s.cc_academic_year = {{ var("current_academic_year") }}
    )

select distinct * except (student_number_grad, state_studentnumber_grad),
from roster as r
left join
    {{ ref("int_assessments__graduation_requirements") }} as f
    on r.student_number = f.student_number_grad

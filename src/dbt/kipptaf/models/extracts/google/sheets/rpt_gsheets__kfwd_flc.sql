with
    act_valid as (
        select distinct r.student_number, r.contact_id, 'Yes' as valid_act,
        from {{ ref("int_kippadb__standardized_test_unpivot") }} as adb
        left join {{ ref("int_kippadb__roster") }} as r on adb.contact = r.contact_id
        where adb.score_type = 'act_composite'
    )

select
    co.student_number,
    co.lastfirst as student_name,
    co.school_abbreviation as school,
    co.region,
    co.advisor_lastfirst as advisor,
    co.gender,
    co.student_email_google,

    ce.teacher_lastfirst as ccr_teacher,
    ce.sections_external_expression as ccr_period,

    kt.contact_owner_name as counselor_name,
    kt.contact_college_match_display_gpa,
    kt.contact_highest_act_score,

    coalesce(kt.contact_id, 'not in salesforce') as sf_id,
    case when co.spedlep like 'SPED%' then 'Has IEP' else 'No IEP' end as iep_status,
    case
        when co.enroll_status = 0
        then 'currently enrolled'
        when co.enroll_status = 2
        then 'transferred out'
    end as enroll_status,
    concat(co.lastfirst, ' - ', co.student_number) as student_identifier,
    act.valid_act,
from {{ ref("base_powerschool__student_enrollments") }} as co
left join
    {{ ref("int_kippadb__roster") }} as kt on co.student_number = kt.student_number
left join
    {{ ref("base_powerschool__course_enrollments") }} as ce
    on co.student_number = ce.students_student_number
    and co.academic_year = ce.cc_academic_year
    and ce.courses_course_name like 'College and Career%'
    and ce.rn_course_number_year = 1
    and not ce.is_dropped_section
left join act_valid as act on kt.contact_id = act.contact_id
where
    co.academic_year = {{ var("current_academic_year") }}
    and co.rn_year = 1
    and co.grade_level = 11

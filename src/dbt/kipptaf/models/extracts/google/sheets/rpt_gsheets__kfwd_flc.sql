with
    act_valid as (
        select r.student_number, r.contact_id, count(adb.score_type) as act_count,
        from {{ ref("int_kippadb__standardized_test_unpivot") }} as adb
        left join {{ ref("int_kippadb__roster") }} as r on adb.contact = r.contact_id
        where adb.score_type = 'act_composite'
        group by r.student_number, r.contact_id
    ),

    early as (
        select applicant, max(is_early_action_decision) as is_ea_ed,
        from {{ ref("base_kippadb__application") }}
        group by applicant
    ),

    matriculated_application as (
        select
            applicant,
            adjusted_6_year_minority_graduation_rate as matriculated_ecc,
            row_number() over (partition by applicant order by id asc) as rn_applicant,
        from {{ ref("base_kippadb__application") }}
        where
            matriculation_decision = 'Matriculated (Intent to Enroll)'
            and intended_degree_type = "Bachelor's (4-year)"
    ),

    bgp as (
        select
            contact,
            subject as bgp,
            row_number() over (partition by contact order by date desc) as rn_bgp,
        from {{ ref("stg_kippadb__contact_note") }}
        where
            subject in (
                'BGP: 2-year',
                'BGP: 4-year',
                'BGP: CTE',
                'BGP: Workforce',
                'BGP: Unknown',
                'BGP: Military'
            )
    )

select  -- noqa: ST06
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
    act.act_count,
    co.lep_status,
    case
        when kt.contact_college_match_display_gpa >= 3.50
        then '3.50+'
        when kt.contact_college_match_display_gpa >= 3.00
        then '3.00-3.49'
        when kt.contact_college_match_display_gpa >= 2.50
        then '2.50-2.99'
        when kt.contact_college_match_display_gpa >= 2.00
        then '2.00-2.50'
        when kt.contact_college_match_display_gpa < 2.00
        then '<2.00'
    end as hs_gpa_bands,
    coalesce(e.is_ea_ed, false) as is_ea_ed,
    m.matriculated_ecc,
    co.grade_level,
    coalesce(bg.bgp, 'No BGP') as bgp,
    kt.contact_expected_hs_graduation,
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
left join early as e on kt.contact_id = e.applicant
left join
    matriculated_application as m on kt.contact_id = m.applicant and m.rn_applicant = 1
left join bgp as bg on kt.contact_id = bg.contact and bg.rn_bgp = 1
where
    co.academic_year = {{ var("current_academic_year") }}
    and co.rn_year = 1
    and co.grade_level >= 9
    and co.grade_level != 99

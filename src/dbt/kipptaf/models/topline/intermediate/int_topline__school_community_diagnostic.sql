select
    se.student_number,
    se.academic_year,
    se.schoolid,
    
    round(avg(ac.response_int), 1) as average_rating
from {{ ref("int_surveys__survey_responses") }} as sr
inner join
    {{ ref("base_powerschool__student_enrollments") }} as se
    on sr.respondent_email = se.student_email_google
    and sr.academic_year = se.academic_year
    and se.rn_year = 1
    and se.is_enrolled_y1
left join
    {{ ref("stg_surveys__scd_answer_crosswalk") }} as ac
    on sr.question_shortname = ac.question_code
    and sr.answer = ac.response
where
    sr.survey_title = 'School Community Diagnostic Student Survey'
    and sr.question_shortname like '%scd%'
group by se.student_number, se.academic_year, se.schoolid

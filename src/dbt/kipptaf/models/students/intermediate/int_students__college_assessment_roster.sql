select
    e._dbt_source_relation,
    e.academic_year,
    e.student_number,
    e.studentid,
    e.students_dcid,
    e.salesforce_id,
    e.grade_level,

    a.administration_round,
    a.test_type,
    a.test_date,
    a.test_month,
    a.scope,
    a.subject_area,
    a.course_discipline,
    a.score_type,
    a.scale_score,
    a.rn_highest,
    a.max_scale_score,
    a.superscore,

    s.admin_season,

    case
        s.admin_season when 'BOY' then 1 when 'MOY' then 2 else 3
    end as admin_season_order,

from {{ ref("int_extracts__student_enrollments") }} as e
inner join
    {{ ref("int_assessments__college_assessment") }} as a
    on e.academic_year = a.academic_year
    and e.student_number = a.student_number
left join
    {{ ref("stg_google_sheets__kippfwd_seasons") }} as s
    on a.scope = s.scope
    and a.test_month = s.test_month
    and e.grade_level = s.grade_level
where e.school_level = 'HS' and e.rn_year = 1

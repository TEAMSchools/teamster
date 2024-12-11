select
    e.id as enrollment_id,

    r.id as contact_id,

    s.exitdate as actual_end_date,
    s.grade_level as exit_grade_level,

    'Transferred Out' as status,
from {{ ref("stg_kippadb__enrollment") }} as e
inner join {{ ref("stg_kippadb__contact") }} as r on e.student = r.id
inner join
    {{ ref("stg_powerschool__students") }} as s
    on r.school_specific_id = s.student_number
    and s.enroll_status != 0
where
    e.type = 'High School'
    and e.status = 'Attending'
    and e.account_type = 'KIPP High School'

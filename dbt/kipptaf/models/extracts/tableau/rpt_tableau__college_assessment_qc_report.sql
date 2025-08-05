select
    e.student_number,
    e.first_name,
    e.last_name,
    e.dob,
    e.gender,

    p.cb_id,
    p.powerschool_student_number as xwalk_student_number,
    p.gender as cb_gender,
    p.birth_date as cb_dob,

    left(e.middle_name, 1) as middle_initial,

    concat(
        e.last_name, ', ', e.first_name, ' ', left(e.middle_name, 1)
    ) as student_name,

    initcap(p.name_first) as cb_first_name,
    initcap(p.name_mi) as cb_middle_name,
    initcap(p.name_last) as cb_last_name,

    concat(
        initcap(p.name_last), ', ', initcap(p.name_first), ' ', initcap(p.name_mi)
    ) as cb_student_name,
from {{ ref("base_powerschool__student_enrollments") }} as e
left join {{ ref("int_collegeboard__psat") }} as p on e.student_number = p.secondary_id
where e.rn_undergrad = 1 and e.region != 'Miami'

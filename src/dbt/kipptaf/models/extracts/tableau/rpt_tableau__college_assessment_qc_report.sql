with
    psat as (
        select
            cb_id,
            secondary_id,
            test_type,
            powerschool_student_number,
            birth_date,
            gender,
        from {{ ref("int_collegeboard__psat_unpivot") }}
    )

select
    e.student_number,
    e.first_name,
    e.middle_name,
    e.last_name,
    e.dob,
    e.gender,
    p.cb_id,
    p.powerschool_student_number as xwalk_student_number,
    p.birth_date as cb_dob,
    p.gender as cb_gender,
    p.test_type as cb_test_type,
from {{ ref("base_powerschool__student_enrollments") }} as e
left join psat as p on e.student_number = p.secondary_id
where e.rn_undergrad = 1

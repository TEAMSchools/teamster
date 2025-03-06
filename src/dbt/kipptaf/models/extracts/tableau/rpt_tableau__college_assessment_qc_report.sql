with
    psat as (
        select cb_id, secondary_id, test_name, powerschool_student_number, birth_date,
        from {{ ref("stg_collegeboard__psat_unpivot") }}
    )

select student_number, first_name, middle_name, last_name, dob, gender,
from {{ ref("base_powerschool__student_enrollments") }}
where rn_undergrad = 1

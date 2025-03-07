with
    psat as (
        select
            cb_id,
            secondary_id,
            powerschool_student_number as xwalk_student_number,
            gender as cb_gender,
            birth_date as cb_dob,

            initcap(name_first) as cb_first_name,
            initcap(name_mi) as cb_middle_name,
            initcap(name_last) as cb_last_name,

            concat(
                initcap(name_last), ', ', initcap(name_first), ' ', initcap(name_mi)
            ) as cb_student_name,

            row_number() over (partition by secondary_id, test_type) as rn_distinct,

        from {{ ref("int_collegeboard__psat_unpivot") }}
    ),

    roster as (
        select
            e.student_number,
            e.first_name,
            e.last_name,
            e.dob,
            e.gender,
            p.cb_id,
            p.xwalk_student_number,
            p.cb_student_name,
            p.cb_first_name,
            p.cb_middle_name,
            p.cb_last_name,
            p.cb_gender,
            p.cb_dob,

            left(e.middle_name, 1) as middle_initial,

            concat(
                e.last_name, ', ', e.first_name, ' ', left(e.middle_name, 1)
            ) as student_name,

        from {{ ref("base_powerschool__student_enrollments") }} as e
        left join psat as p on e.student_number = p.secondary_id and p.rn_distinct = 1
        where e.rn_undergrad = 1 and e.region != 'Miami'
    )

select *,
from roster

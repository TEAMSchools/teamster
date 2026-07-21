with
    parent_contacts as (
        select
            sc.contact_first_name,
            sc.contact_last_name,
            sc.email,
            sc.phone_home,
            sc.phone_work,
            sc.phone_mobile,
            sc.relationship,
            sc._dbt_source_project,

            safe_cast(xw.powerschool_student_number as int64) as student_number,
        from {{ ref("int_finalsite__student_contacts") }} as sc
        inner join
            {{ ref("int_finalsite__contact_id_attributes") }} as xw
            on sc.finalsite_enrollment_id = xw.finalsite_enrollment_id
            and sc._dbt_source_project = xw._dbt_source_project
        where
            sc.contact_slot = 'contact_1'
            and sc._dbt_source_project in ('kippnewark', 'kippcamden', 'kipppaterson')
            and xw.powerschool_student_number is not null
    ),

    enrolled_students as (
        select
            student_number,

            {{ extract_code_location("stg_powerschool__students") }}
            as _dbt_source_project,
        from {{ ref("stg_powerschool__students") }}
        where enroll_status = 0
    )

select
    pc.student_number as `StudentID`,
    pc.contact_first_name as `ParentFirstName`,
    pc.contact_last_name as `ParentLastName`,
    pc.phone_home as `HomePhone`,
    pc.phone_work as `WorkPhone`,
    pc.phone_mobile as `CellPhone`,
    pc.email as `Email`,
    pc.relationship as `Relationship`,

    cast(null as string) as `Language`,
from parent_contacts as pc
inner join
    enrolled_students as s
    on pc.student_number = s.student_number
    and pc._dbt_source_project = s._dbt_source_project

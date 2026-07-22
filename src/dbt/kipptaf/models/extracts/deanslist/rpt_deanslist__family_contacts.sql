with
    contacts as (
        select
            sc.contact_first_name,
            sc.contact_last_name,
            sc.email,
            sc.phone_home,
            sc.phone_work,
            sc.phone_mobile,
            sc._dbt_source_project,

            safe_cast(xw.powerschool_student_number as int64) as student_number,

            case
                sc.contact_slot
                when 'emergency_1'
                then 'Emergency 1'
                when 'emergency_2'
                then 'Emergency 2'
                when 'emergency_3'
                then 'Emergency 3'
                when 'emergency_4'
                then 'Emergency 4'
                else sc.relationship
            end as relationship,
        from {{ ref("int_finalsite__student_contacts") }} as sc
        inner join
            {{ ref("int_finalsite__contact_id_attributes") }} as xw
            on sc.finalsite_enrollment_id = xw.finalsite_enrollment_id
            and sc._dbt_source_project = xw._dbt_source_project
        where
            sc._dbt_source_project in ('kippnewark', 'kippcamden', 'kipppaterson')
            and xw.powerschool_student_number is not null
    ),

    enrolled_students as (
        -- _dbt_source_project derived inline rather than via extract_code_location
        -- so this CTE stays unit-testable: the macro qualifies _dbt_source_relation
        -- by table name, which dbt unit tests rename to the mock relation.
        select
            student_number,

            regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,
        from {{ ref("stg_powerschool__students") }}
        where enroll_status = 0
    )

select
    c.student_number as `StudentID`,
    c.contact_first_name as `ParentFirstName`,
    c.contact_last_name as `ParentLastName`,
    c.phone_home as `HomePhone`,
    c.phone_work as `WorkPhone`,
    c.phone_mobile as `CellPhone`,
    c.email as `Email`,
    c.relationship as `Relationship`,

    cast(null as string) as `Language`,
from contacts as c
inner join
    enrolled_students as s
    on c.student_number = s.student_number
    and c._dbt_source_project = s._dbt_source_project

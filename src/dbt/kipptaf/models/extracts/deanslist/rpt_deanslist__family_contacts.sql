with
    contacts as (
        select
            sc.contact_first_name,
            sc.contact_last_name,
            sc.email,
            sc._dbt_source_project,

            safe_cast(xw.powerschool_student_number as int64) as student_number,

            -- DeansList phone fields accept only digits and `x` (extension); strip
            -- the E.164 canonical (leading `+`, etc.) to that shape.
            regexp_replace(lower(sc.phone_home), r'[^0-9x]', '') as phone_home,
            regexp_replace(lower(sc.phone_work), r'[^0-9x]', '') as phone_work,
            regexp_replace(lower(sc.phone_mobile), r'[^0-9x]', '') as phone_mobile,

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
    {{ ref("stg_powerschool__students") }} as s
    on c.student_number = s.student_number
    and c._dbt_source_project = s._dbt_source_project
    and s.enroll_status = 0

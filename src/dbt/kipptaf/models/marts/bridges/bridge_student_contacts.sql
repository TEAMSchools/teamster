with
    contacts_union as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "int_powerschool__contacts"),
                    source("kippcamden_powerschool", "int_powerschool__contacts"),
                    source("kippmiami_powerschool", "int_powerschool__contacts"),
                    source("kipppaterson_powerschool", "int_powerschool__contacts"),
                ]
            )
        }}
    ),

    students_union as (
        select _dbt_source_relation, dcid, student_number,
        from {{ ref("stg_powerschool__students") }}
    )

select
    {{ dbt_utils.generate_surrogate_key(["s.student_number"]) }} as student_key,

    {{ dbt_utils.generate_surrogate_key(["c._dbt_source_relation", "c.personid"]) }}
    as student_contact_person_key,

    c.relationship_type,
    c.contactpriorityorder as contact_priority,

    c.isemergency = 1 as is_emergency,
    c.schoolpickupflg = 1 as is_pickup,
    c.iscustodial = 1 as is_custodial,
    c.liveswithflg = 1 as lives_with,

from contacts_union as c
inner join
    students_union as s
    on c.studentdcid = s.dcid
    and {{ union_dataset_join_clause(left_alias="c", right_alias="s") }}
where c.person_type != 'self'

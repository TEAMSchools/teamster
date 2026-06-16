with
    students_union as (
        select _dbt_source_relation, dcid, student_number,
        from {{ ref("stg_powerschool__students") }}
    )

select
    {{ dbt_utils.generate_surrogate_key(["s.student_number"]) }} as student_key,

    {{ dbt_utils.generate_surrogate_key(["c._dbt_source_project", "c.personid"]) }}
    as student_contact_person_key,

    c.relationship_type,
    c.contactpriorityorder as priority,

    c.isemergency = 1 as is_emergency,
    c.schoolpickupflg = 1 as is_pickup,
    c.iscustodial = 1 as is_custodial,
    c.liveswithflg = 1 as is_household_member,

from {{ ref("int_powerschool__contacts") }} as c
inner join
    students_union as s
    on c.studentdcid = s.dcid
    and {{ union_dataset_join_clause(left_alias="c", right_alias="s") }}
where c.person_type != 'self'

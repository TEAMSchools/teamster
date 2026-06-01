with
    contacts_relations as (
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

    -- trunk-ignore(sqlfluff/ST03): referenced by string in dbt_utils.deduplicate
    contacts_union as (
        select ur.*, {{ extract_code_location("ur") }} as _dbt_source_project,
        from contacts_relations as ur
    ),

    person_contacts_union as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool", "int_powerschool__person_contacts"
                    ),
                    source(
                        "kippcamden_powerschool", "int_powerschool__person_contacts"
                    ),
                    source(
                        "kippmiami_powerschool", "int_powerschool__person_contacts"
                    ),
                    source(
                        "kipppaterson_powerschool", "int_powerschool__person_contacts"
                    ),
                ]
            )
        }}
    ),

    contacts_deduped as (
        {{
            dbt_utils.deduplicate(
                relation="contacts_union",
                partition_by="_dbt_source_relation, personid",
                order_by="contactpriorityorder asc",
            )
        }}
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced by string in dbt_utils.deduplicate
    phone_ranked as (
        select
            _dbt_source_relation,
            personid,
            priority_order,
            contact as phone,

            case
                contact_type
                when 'Mobile'
                then 1
                when 'Home'
                then 2
                when 'Daytime'
                then 3
                when 'Work'
                then 4
                else 5
            end as type_rank,
        from person_contacts_union
        where
            contact_category = 'Phone'
            and contact_type in ('Mobile', 'Home', 'Daytime', 'Work', 'Not Set')
            and is_primary = 1
    ),

    phone as (
        {{
            dbt_utils.deduplicate(
                relation="phone_ranked",
                partition_by="_dbt_source_relation, personid",
                order_by="type_rank asc, priority_order asc",
            )
        }}
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced by string in dbt_utils.deduplicate
    email_all as (
        select _dbt_source_relation, personid, contact as email, priority_order,
        from person_contacts_union
        where contact_category = 'Email' and contact_type = 'Current'
    ),

    email as (
        {{
            dbt_utils.deduplicate(
                relation="email_all",
                partition_by="_dbt_source_relation, personid",
                order_by="priority_order asc",
            )
        }}
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced by string in dbt_utils.deduplicate
    address_all as (
        select _dbt_source_relation, personid, contact as address, priority_order,
        from person_contacts_union
        where contact_category = 'Address' and contact_type = 'Home'
    ),

    address as (
        {{
            dbt_utils.deduplicate(
                relation="address_all",
                partition_by="_dbt_source_relation, personid",
                order_by="priority_order asc",
            )
        }}
    )

select
    {{ dbt_utils.generate_surrogate_key(["c._dbt_source_project", "c.personid"]) }}
    as student_contact_person_key,

    c.contact_name as full_name,

    ph.phone,
    em.email,

    ad.address as home_address,
from contacts_deduped as c
left join
    phone as ph
    on c.personid = ph.personid
    and {{ union_dataset_join_clause(left_alias="c", right_alias="ph") }}
left join
    email as em
    on c.personid = em.personid
    and {{ union_dataset_join_clause(left_alias="c", right_alias="em") }}
left join
    address as ad
    on c.personid = ad.personid
    and {{ union_dataset_join_clause(left_alias="c", right_alias="ad") }}
where c.person_type != 'self'

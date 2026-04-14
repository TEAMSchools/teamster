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
    {{ dbt_utils.generate_surrogate_key(["c._dbt_source_relation", "c.personid"]) }}
    as student_contact_person_key,

    c._dbt_source_relation,
    c.personid as powerschool_person_id,
    c.contact_name,

    ph.phone,
    em.email,
    ad.address,
from contacts_deduped as c
left join
    phone as ph
    on c._dbt_source_relation = ph._dbt_source_relation
    and c.personid = ph.personid
left join
    email as em
    on c._dbt_source_relation = em._dbt_source_relation
    and c.personid = em.personid
left join
    address as ad
    on c._dbt_source_relation = ad._dbt_source_relation
    and c.personid = ad.personid
where c.person_type != 'self'

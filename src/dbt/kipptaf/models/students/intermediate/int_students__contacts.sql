with
    -- NJ Finalsite branch: the SIS-agnostic student-contacts union (cutover
    -- regions only — the region scope lives in int_finalsite__student_contacts),
    -- reduced to enrolled students by crosswalking the Finalsite enrollment id
    -- to a PowerSchool student number. The crosswalk union also carries Miami's
    -- Focus contacts, but they never match here because
    -- int_finalsite__student_contacts unions only cutover regions.
    -- Phone columns here are E.164-normalized upstream (clean_phone); the
    -- powerschool branch below passes phones through raw, so this model's phone
    -- columns are mixed-format by source region.
    finalsite as (
        select
            fc.contact_slot,
            fc.finalsite_contact_id,
            fc.contact_name,
            fc.relationship,
            fc.phone_mobile,
            fc.phone_home,
            fc.phone_daytime,
            fc.phone_work,
            fc.phone_primary,
            fc.is_emergency,
            fc.is_pickup,
            fc.is_custodial,
            fc.is_household_member,
            fc._dbt_source_project,
            fc.email as email_current,
            fc.home_address as address_home,

            cast(null as string) as personid,

            safe_cast(xw.powerschool_student_number as int64) as student_number,
        from {{ ref("int_finalsite__student_contacts") }} as fc
        inner join
            {{ ref("int_finalsite__contact_id_attributes") }} as xw
            on fc.finalsite_enrollment_id = xw.finalsite_enrollment_id
            and fc._dbt_source_project = xw._dbt_source_project
        where xw.powerschool_student_number is not null
    ),

    -- PowerSchool-mapped branch: regions not yet cut over to Finalsite (today
    -- Miami only — the NJ regions Newark, Camden, and Paterson are all
    -- Finalsite-sourced). Mirrors the legacy pivot slotting: contact_1 is the
    -- priority-1 contact; emergency_N are the priority>=3 emergency contacts
    -- ranked by priority. Remove a region from the filter below as it cuts over
    -- to Finalsite.
    ps_base as (
        select
            _dbt_source_relation,
            _dbt_source_project,
            studentdcid,
            personid,
            contact_name,
            relationship_type,
            contactpriorityorder,

            isemergency = 1 as is_emergency,
            iscustodial = 1 as is_custodial,
            liveswithflg = 1 as is_household_member,
            schoolpickupflg = 1 as is_pickup,
        from {{ ref("int_powerschool__contacts") }}
        where
            person_type != 'self'
            and _dbt_source_project not in ('kippnewark', 'kippcamden', 'kipppaterson')
    ),

    ps_contact_1 as (
        select *, 'contact_1' as contact_slot,
        from ps_base
        where contactpriorityorder = 1
    ),

    ps_emergency_ranked as (
        select
            *,

            row_number() over (
                partition by _dbt_source_relation, studentdcid
                order by contactpriorityorder asc
            ) as emergency_rank,
        from ps_base
        where contactpriorityorder >= 3 and is_emergency
    ),

    ps_emergency as (
        select
            * except (emergency_rank),

            concat('emergency_', cast(emergency_rank as string)) as contact_slot,
        from ps_emergency_ranked
        where emergency_rank <= 4
    ),

    ps_slotted as (
        select
            _dbt_source_relation,
            _dbt_source_project,
            studentdcid,
            personid,
            contact_name,
            relationship_type,
            contact_slot,
            is_emergency,
            is_custodial,
            is_household_member,
            is_pickup,
        from ps_contact_1

        union all

        select
            _dbt_source_relation,
            _dbt_source_project,
            studentdcid,
            personid,
            contact_name,
            relationship_type,
            contact_slot,
            is_emergency,
            is_custodial,
            is_household_member,
            is_pickup,
        from ps_emergency
    ),

    -- Only Miami still sources contacts from PowerSchool; the NJ regions are
    -- Finalsite-sourced and drop out of ps_base above, so their person-contact
    -- enrichment rows would never match. Add a region back here if it reverts
    -- to the PowerSchool branch.
    ps_person_contacts as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippmiami_powerschool", "int_powerschool__person_contacts"
                    ),
                ]
            )
        }}
    ),

    ps_methods_ranked as (
        select
            _dbt_source_relation,
            personid,
            contact_category,
            contact_type,
            contact,

            row_number() over (
                partition by
                    _dbt_source_relation, personid, contact_category, contact_type
                order by is_primary desc, priority_order asc
            ) as method_rank,
        from ps_person_contacts
    ),

    ps_typed as (
        select
            _dbt_source_relation,
            personid,

            max(
                if(
                    contact_category = 'Phone' and contact_type = 'Mobile',
                    contact,
                    null
                )
            ) as phone_mobile,
            max(
                if(contact_category = 'Phone' and contact_type = 'Home', contact, null)
            ) as phone_home,
            max(
                if(
                    contact_category = 'Phone' and contact_type = 'Daytime',
                    contact,
                    null
                )
            ) as phone_daytime,
            max(
                if(contact_category = 'Phone' and contact_type = 'Work', contact, null)
            ) as phone_work,
            max(
                if(
                    contact_category = 'Email' and contact_type = 'Current',
                    contact,
                    null
                )
            ) as email_current,
            max(
                if(
                    contact_category = 'Address' and contact_type = 'Home',
                    contact,
                    null
                )
            ) as address_home,
        from ps_methods_ranked
        where method_rank = 1
        group by _dbt_source_relation, personid
    ),

    ps_primary_phone_ranked as (
        select
            _dbt_source_relation,
            personid,
            contact as phone_primary,

            row_number() over (
                partition by _dbt_source_relation, personid
                order by is_primary desc, priority_order asc
            ) as phone_rank,
        from ps_person_contacts
        where contact_category = 'Phone'
    ),

    ps_primary_phone as (
        select _dbt_source_relation, personid, phone_primary,
        from ps_primary_phone_ranked
        where phone_rank = 1
    ),

    students as (
        select _dbt_source_relation, dcid, student_number,
        from {{ ref("stg_powerschool__students") }}
        where dcid >= 1
    ),

    powerschool as (
        select
            sl.contact_slot,
            sl.contact_name,
            sl.relationship_type as relationship,
            sl.is_emergency,
            sl.is_pickup,
            sl.is_custodial,
            sl.is_household_member,
            sl._dbt_source_project,

            pt.phone_mobile,
            pt.phone_home,
            pt.phone_daytime,
            pt.phone_work,
            pt.email_current,
            pt.address_home,

            pp.phone_primary,

            s.student_number,

            cast(sl.personid as string) as personid,
            cast(null as string) as finalsite_contact_id,
        from ps_slotted as sl
        inner join
            students as s
            on sl.studentdcid = s.dcid
            and {{ union_dataset_join_clause(left_alias="sl", right_alias="s") }}
        left join
            ps_typed as pt
            on sl.personid = pt.personid
            and {{ union_dataset_join_clause(left_alias="sl", right_alias="pt") }}
        left join
            ps_primary_phone as pp
            on sl.personid = pp.personid
            and {{ union_dataset_join_clause(left_alias="sl", right_alias="pp") }}
    )

select
    student_number,
    _dbt_source_project,
    contact_slot,
    personid,
    finalsite_contact_id,
    contact_name,
    relationship,
    email_current,
    phone_mobile,
    phone_home,
    phone_daytime,
    phone_work,
    phone_primary,
    address_home,
    is_emergency,
    is_pickup,
    is_custodial,
    is_household_member,
from finalsite

union all

select
    student_number,
    _dbt_source_project,
    contact_slot,
    personid,
    finalsite_contact_id,
    contact_name,
    relationship,
    email_current,
    phone_mobile,
    phone_home,
    phone_daytime,
    phone_work,
    phone_primary,
    address_home,
    is_emergency,
    is_pickup,
    is_custodial,
    is_household_member,
from powerschool

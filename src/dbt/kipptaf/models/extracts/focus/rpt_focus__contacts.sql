with
    guardians as (
        select
            rel.relationship_id,
            rel.rel_type as student_relation,

            g.first_name,
            g.middle_name,
            g.last_name,
            g.email,
            g.gender as contact_gender,
            g.household_ids,
            g.phone_1_type as contact1_type,
            g.phone_1_number as contact1_value,
            g.phone_2_type as contact2_type,
            g.phone_2_number as contact2_value,

            ida.focus_student_id_prefixed as student_id,

            aor.address_1 as address,
            aor.address_2 as address2,
            aor.city,
            aor.state,
            aor.zip as zipcode,

            0 as contact_group,

            cast(null as string) as contact3_type,
            cast(null as string) as contact3_value,

            if(rel.is_primary, 0, 1) as group_rank,
        from {{ ref("stg_finalsite__contact_relationships") }} as rel
        inner join
            {{ ref("stg_finalsite__contacts") }} as g
            on rel.rel_id = g.finalsite_enrollment_id
        inner join
            {{ ref("int_finalsite__enrollment_lifecycle") }} as l
            on rel.finalsite_enrollment_id = l.finalsite_enrollment_id
        inner join
            {{ ref("int_finalsite__contact_id_attributes") }} as ida
            on rel.finalsite_enrollment_id = ida.finalsite_enrollment_id
            and ida.focus_student_id_prefixed is not null
        -- the guardian's own household linkage decides their address; array
        -- position does not identify Finalsite's primary household.
        -- Unresolved keeps the row and nulls the address — the feed is
        -- import-once, so a wrong address is permanent, while the name,
        -- relationship, email, and phones are still worth sending.
        left join
            {{ ref("int_finalsite__contact_address_of_record") }} as aor
            on rel.rel_id = aor.finalsite_enrollment_id
        inner join
            {{ ref("stg_finalsite__contacts") }} as stu
            on rel.finalsite_enrollment_id = stu.finalsite_enrollment_id
            and stu.status = 'enrolled'
        where
            rel.rel_type in (
                'parent',
                'guardian',
                'grandparent',
                'stepparent',
                'relative',
                'aunt/uncle'
            )
    ),

    emergency_long as (
        -- Positional passthrough: emergency_N is the emrg_N custom-field set
        -- as-is. Finalsite emergency contacts are custom fields on the
        -- student's own record, not relationship rows, so they never reach the
        -- relationship-type filter above. The shape here mirrors
        -- int_finalsite__student_contacts, which cannot be ref'd — it excludes
        -- Miami to avoid double-counting against the PowerSchool branch of
        -- int_students__contacts.
        select
            a.emrg_1_name_first_name as first_name,
            a.emrg_1_name_middle_name as middle_name,
            a.emrg_1_name_last_name as last_name,
            a.emrg_1_email as email,
            a.emrg_1_phone_1_type as contact1_type,
            a.emrg_1_phone_1_number as contact1_value,
            a.emrg_1_phone_2_type as contact2_type,
            a.emrg_1_phone_2_number as contact2_value,
            a.emrg_1_phone_3_type as contact3_type,
            a.emrg_1_phone_3_number as contact3_value,

            ida.focus_student_id_prefixed as student_id,

            1 as contact_group,
            1 as group_rank,

            cast(null as string) as relationship_id,
            cast(null as string) as address,
            cast(null as string) as address2,
            cast(null as string) as city,
            cast(null as string) as state,
            cast(null as string) as zipcode,
            cast(null as string) as contact_gender,
            cast(null as array<string>) as household_ids,

            coalesce(
                a.emrg_1_relationship_ss, a.emrg_1_relationship_txt
            ) as student_relation,
        from {{ ref("int_finalsite__contact_custom_attributes") }} as a
        inner join
            {{ ref("int_finalsite__enrollment_lifecycle") }} as l
            on a.finalsite_enrollment_id = l.finalsite_enrollment_id
        inner join
            {{ ref("int_finalsite__contact_id_attributes") }} as ida
            on a.finalsite_enrollment_id = ida.finalsite_enrollment_id
            and ida.focus_student_id_prefixed is not null
        inner join
            {{ ref("stg_finalsite__contacts") }} as stu
            on a.finalsite_enrollment_id = stu.finalsite_enrollment_id
            and stu.status = 'enrolled'
        where a.emrg_1_name_first_name is not null and a.emrg_1_name_first_name != ''

        union all

        select
            a.emrg_2_name_first_name as first_name,
            a.emrg_2_name_middle_name as middle_name,
            a.emrg_2_name_last_name as last_name,
            a.emrg_2_email as email,
            a.emrg_2_phone_1_type as contact1_type,
            a.emrg_2_phone_1_number as contact1_value,
            a.emrg_2_phone_2_type as contact2_type,
            a.emrg_2_phone_2_number as contact2_value,
            a.emrg_2_phone_3_type as contact3_type,
            a.emrg_2_phone_3_number as contact3_value,

            ida.focus_student_id_prefixed as student_id,

            1 as contact_group,
            2 as group_rank,

            cast(null as string) as relationship_id,
            cast(null as string) as address,
            cast(null as string) as address2,
            cast(null as string) as city,
            cast(null as string) as state,
            cast(null as string) as zipcode,
            cast(null as string) as contact_gender,
            cast(null as array<string>) as household_ids,

            coalesce(
                a.emrg_2_relationship_ss, a.emrg_2_relationship_txt
            ) as student_relation,
        from {{ ref("int_finalsite__contact_custom_attributes") }} as a
        inner join
            {{ ref("int_finalsite__enrollment_lifecycle") }} as l
            on a.finalsite_enrollment_id = l.finalsite_enrollment_id
        inner join
            {{ ref("int_finalsite__contact_id_attributes") }} as ida
            on a.finalsite_enrollment_id = ida.finalsite_enrollment_id
            and ida.focus_student_id_prefixed is not null
        inner join
            {{ ref("stg_finalsite__contacts") }} as stu
            on a.finalsite_enrollment_id = stu.finalsite_enrollment_id
            and stu.status = 'enrolled'
        where a.emrg_2_name_first_name is not null and a.emrg_2_name_first_name != ''

        union all

        select
            a.emrg_3_name_first_name as first_name,
            cast(null as string) as middle_name,
            a.emrg_3_name_last_name as last_name,
            a.emrg_3_email as email,
            a.emrg_3_phone_1_type as contact1_type,
            a.emrg_3_phone_1_number as contact1_value,
            a.emrg_3_phone_2_type as contact2_type,
            a.emrg_3_phone_2_number as contact2_value,
            a.emrg_3_phone_3_type as contact3_type,
            a.emrg_3_phone_3_number as contact3_value,

            ida.focus_student_id_prefixed as student_id,

            1 as contact_group,
            3 as group_rank,

            cast(null as string) as relationship_id,
            cast(null as string) as address,
            cast(null as string) as address2,
            cast(null as string) as city,
            cast(null as string) as state,
            cast(null as string) as zipcode,
            cast(null as string) as contact_gender,
            cast(null as array<string>) as household_ids,

            coalesce(
                a.emrg_3_relationship_ss, a.emrg_3_relationship_txt
            ) as student_relation,
        from {{ ref("int_finalsite__contact_custom_attributes") }} as a
        inner join
            {{ ref("int_finalsite__enrollment_lifecycle") }} as l
            on a.finalsite_enrollment_id = l.finalsite_enrollment_id
        inner join
            {{ ref("int_finalsite__contact_id_attributes") }} as ida
            on a.finalsite_enrollment_id = ida.finalsite_enrollment_id
            and ida.focus_student_id_prefixed is not null
        inner join
            {{ ref("stg_finalsite__contacts") }} as stu
            on a.finalsite_enrollment_id = stu.finalsite_enrollment_id
            and stu.status = 'enrolled'
        where a.emrg_3_name_first_name is not null and a.emrg_3_name_first_name != ''

        union all

        select
            a.emrg_4_name_first_name as first_name,
            cast(null as string) as middle_name,
            a.emrg_4_name_last_name as last_name,
            a.emrg_4_email as email,
            a.emrg_4_phone_1_type as contact1_type,
            a.emrg_4_phone_1_number as contact1_value,
            a.emrg_4_phone_2_type as contact2_type,
            a.emrg_4_phone_2_number as contact2_value,
            a.emrg_4_phone_3_type as contact3_type,
            a.emrg_4_phone_3_number as contact3_value,

            ida.focus_student_id_prefixed as student_id,

            1 as contact_group,
            4 as group_rank,

            cast(null as string) as relationship_id,
            cast(null as string) as address,
            cast(null as string) as address2,
            cast(null as string) as city,
            cast(null as string) as state,
            cast(null as string) as zipcode,
            cast(null as string) as contact_gender,
            cast(null as array<string>) as household_ids,

            coalesce(
                a.emrg_4_relationship_ss, a.emrg_4_relationship_txt
            ) as student_relation,
        from {{ ref("int_finalsite__contact_custom_attributes") }} as a
        inner join
            {{ ref("int_finalsite__enrollment_lifecycle") }} as l
            on a.finalsite_enrollment_id = l.finalsite_enrollment_id
        inner join
            {{ ref("int_finalsite__contact_id_attributes") }} as ida
            on a.finalsite_enrollment_id = ida.finalsite_enrollment_id
            and ida.focus_student_id_prefixed is not null
        inner join
            {{ ref("stg_finalsite__contacts") }} as stu
            on a.finalsite_enrollment_id = stu.finalsite_enrollment_id
            and stu.status = 'enrolled'
        where a.emrg_4_name_first_name is not null and a.emrg_4_name_first_name != ''
    ),

    all_contacts as (
        select
            student_id,
            relationship_id,
            student_relation,
            first_name,
            middle_name,
            last_name,
            email,
            contact_gender,
            household_ids,
            contact1_type,
            contact1_value,
            contact2_type,
            contact2_value,
            contact3_type,
            contact3_value,
            address,
            address2,
            city,
            state,
            zipcode,
            contact_group,
            group_rank,
        from guardians

        union all

        select
            student_id,
            relationship_id,
            student_relation,
            first_name,
            middle_name,
            last_name,
            email,
            contact_gender,
            household_ids,
            contact1_type,
            contact1_value,
            contact2_type,
            contact2_value,
            contact3_type,
            contact3_value,
            address,
            address2,
            city,
            state,
            zipcode,
            contact_group,
            group_rank,
        from emergency_long
    ),

    crosswalked as (
        -- Focus does not enforce STUDENT_RELATION, and 12 rows of
        -- un-crosswalked lowercase feed values are already sitting in prod
        -- Focus. The accepted_values test on this output is the only gate.
        -- Domain verified against live Focus: 13 values, no 'Emergency'.
        -- Gender is present only on the guardian branch (a guardian's own
        -- stg_finalsite__contacts row); emergency rows are custom fields on
        -- the student's record and fall through to the non-gendered value.
        select
            * except (student_relation, contact_gender),

            case
                when
                    student_relation in (
                        'Mother',
                        'Father',
                        'Parent',
                        'Guardian',
                        'Grandmother',
                        'Grandfather',
                        'Aunt',
                        'Uncle',
                        'Stepfather',
                        'Stepmother',
                        'Stepparent',
                        'Surrogate'
                    )
                then student_relation
                when student_relation = 'parent' and contact_gender in ('F', 'Female')
                then 'Mother'
                when student_relation = 'parent' and contact_gender in ('M', 'Male')
                then 'Father'
                when student_relation = 'parent'
                then 'Parent'
                when
                    student_relation = 'grandparent'
                    and contact_gender in ('F', 'Female')
                then 'Grandmother'
                when
                    student_relation = 'grandparent' and contact_gender in ('M', 'Male')
                then 'Grandfather'
                when
                    student_relation = 'aunt/uncle'
                    and contact_gender in ('F', 'Female')
                then 'Aunt'
                when student_relation = 'aunt/uncle' and contact_gender in ('M', 'Male')
                then 'Uncle'
                when
                    student_relation = 'stepparent'
                    and contact_gender in ('F', 'Female')
                then 'Stepmother'
                when student_relation = 'stepparent' and contact_gender in ('M', 'Male')
                then 'Stepfather'
                when student_relation = 'stepparent'
                then 'Stepparent'
                when student_relation = 'guardian'
                then 'Guardian'
                when student_relation = 'Great Aunt'
                then 'Aunt'
                when student_relation = 'Great Uncle'
                then 'Uncle'
                else 'None'
            end as student_relation,
        from all_contacts
    ),

    household_compared as (
        -- resides_with_stud / custody: the first contact per student is
        -- always Y; a later contact is Y only when it shares a household
        -- with that first contact. Household membership rather than an
        -- address string comparison -- '123 Main St' vs '123 Main Street',
        -- or a unit number that sits in address on one row and address2 on
        -- the other, would both read as a false N. N is an explicit default
        -- when household membership is unknown on either side, not a guess.
        select
            *,

            first_value(household_ids) over (
                partition by student_id
                order by
                    contact_group asc,
                    group_rank asc,
                    last_name asc,
                    first_name asc,
                    relationship_id asc
            ) as first_contact_household_ids,
        from crosswalked
    ),

    household_flagged as (
        select
            * except (household_ids, first_contact_household_ids),

            (
                select count(*),
                from unnest(household_ids) as h
                where h in unnest(first_contact_household_ids)
            ) as shared_household_count,
        from household_compared
    ),

    phones_valid as (
        -- clean_phone already normalized both phone sources to E.164, and its
        -- contract is to never return NULL -- unparseable input passes through
        -- de-garbled. So repeated-digit junk (which is NANP-valid) survives it
        -- as a well-formed +1XXXXXXXXXX. Reject it here rather than in the
        -- macro: the macro is shared by rpt_parentsquare__parents,
        -- rpt_deanslist__family_contacts, and int_students__contacts, and a
        -- guard inside its CASE would emit the raw digits instead of nulling
        -- them. Only repeated digits 2-9 can reach this -- clean_phone's NANP
        -- check already rejects a leading 0 or 1. See #4769 decision Q.
        -- Known limitation: clean_phone appends x<ext> when the source number
        -- carries an extension, so a junk number with an extension would slip
        -- past this exact-match list -- vanishingly rare, not worth expanding
        -- scope over.
        select
            * except (contact1_value, contact2_value, contact3_value),

            if(
                contact1_value in (
                    '+12222222222',
                    '+13333333333',
                    '+14444444444',
                    '+15555555555',
                    '+16666666666',
                    '+17777777777',
                    '+18888888888',
                    '+19999999999'
                ),
                cast(null as string),
                contact1_value
            ) as contact1_value,
            if(
                contact2_value in (
                    '+12222222222',
                    '+13333333333',
                    '+14444444444',
                    '+15555555555',
                    '+16666666666',
                    '+17777777777',
                    '+18888888888',
                    '+19999999999'
                ),
                cast(null as string),
                contact2_value
            ) as contact2_value,
            if(
                contact3_value in (
                    '+12222222222',
                    '+13333333333',
                    '+14444444444',
                    '+15555555555',
                    '+16666666666',
                    '+17777777777',
                    '+18888888888',
                    '+19999999999'
                ),
                cast(null as string),
                contact3_value
            ) as contact3_value,
        from household_flagged
    ),

    phones_typed as (
        -- A blank or unrecognized type defaults to Cell Phone rather than
        -- dropping the contact (#4769 decision J) -- but only when the slot
        -- actually carries a surviving number. A slot with no value (never
        -- had one, or had one and phones_valid junk-rejected it above) gets a
        -- null type instead: there is no contact to guess a type for, and
        -- Task 7 reads this column to decide whether the slot is an SMS
        -- target, so a phantom type on an empty slot would wrongly mark it
        -- one.
        select
            * except (contact1_type, contact2_type, contact3_type),

            case
                when contact1_value is not null
                then {{ focus_phone_type("contact1_type") }}
                else cast(null as string)
            end as contact1_type,
            case
                when contact2_value is not null
                then {{ focus_phone_type("contact2_type") }}
                else cast(null as string)
            end as contact2_type,
            case
                when contact3_value is not null
                then {{ focus_phone_type("contact3_type") }}
                else cast(null as string)
            end as contact3_type,
        from phones_valid
    ),

    ranked as (
        -- Guardians hold ranks 1..N in their existing order, then emergency
        -- slots follow in emrg_1..4 order. Miami populates no
        -- emrg_N_priority_ss at all, so there is nothing to interleave on.
        -- relationship_id is the final tiebreak so two guardians sharing
        -- is_primary and both names get a stable rank between runs.
        select
            *,

            row_number() over (
                partition by student_id
                order by
                    contact_group asc,
                    group_rank asc,
                    last_name asc,
                    first_name asc,
                    relationship_id asc
            ) as sort_order,
        from phones_typed
    ),

    custody_flagged as (
        -- Derived once here and projected as both RESIDES_WITH_STUD and
        -- CUSTODY in the final select below -- BigQuery has no lateral
        -- column aliases, so sort_order (added by ranked, above) can't be
        -- read in the same select list that produces it.
        select
            * except (shared_household_count),

            if(
                sort_order = 1 or shared_household_count > 0, 'Y', 'N'
            ) as lives_with_flag,
        from ranked
    )

-- trunk-ignore(sqlfluff/ST06): column order fixed by Focus CONTACTS contract
select
    student_id,
    student_relation,
    sort_order,

    first_name,
    middle_name,
    last_name,

    lives_with_flag as resides_with_stud,
    lives_with_flag as custody,
    'Y' as emergency,
    'Y' as pickup,

    address,
    address2,
    city,
    state,
    zipcode,
    email,
    contact1_type,
    contact1_value,

    cast(null as string) as contact1_blocked,
    cast(null as string) as contact1_unlisted,
    cast(null as string) as contact1_callout,

    contact2_type,
    contact2_value,

    cast(null as string) as contact2_blocked,
    cast(null as string) as contact2_unlisted,
    cast(null as string) as contact2_callout,

    contact3_type,
    contact3_value,

    cast(null as string) as contact3_blocked,
    cast(null as string) as contact3_unlisted,
    cast(null as string) as contact3_callout,
    cast(null as string) as contact4_type,
    cast(null as string) as contact4_value,
    cast(null as string) as contact4_blocked,
    cast(null as string) as contact4_unlisted,
    cast(null as string) as contact4_callout,
    cast(null as string) as contact5_type,
    cast(null as string) as contact5_value,
    cast(null as string) as contact5_blocked,
    cast(null as string) as contact5_unlisted,
    cast(null as string) as contact5_callout,
    cast(null as string) as contact6_type,
    cast(null as string) as contact6_value,
    cast(null as string) as contact6_blocked,
    cast(null as string) as contact6_unlisted,
    cast(null as string) as contact6_callout,
    cast(null as string) as contact7_type,
    cast(null as string) as contact7_value,
    cast(null as string) as contact7_blocked,
    cast(null as string) as contact7_unlisted,
from custody_flagged

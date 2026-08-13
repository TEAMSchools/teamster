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

            cast(null as string) as resides_with_stud,
            cast(null as string) as custody,
            cast(null as string) as emergency,
            cast(null as string) as pickup,
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
            'Y' as emergency,

            cast(null as string) as relationship_id,
            cast(null as string) as address,
            cast(null as string) as address2,
            cast(null as string) as city,
            cast(null as string) as state,
            cast(null as string) as zipcode,
            cast(null as string) as contact_gender,

            coalesce(
                a.emrg_1_relationship_ss, a.emrg_1_relationship_txt
            ) as student_relation,

            if(a.emrg_1_lives_with_yn, 'Y', null) as resides_with_stud,
            if(a.emrg_1_custody_yn, 'Y', null) as custody,
            if(a.emrg_1_pickup_yn, 'Y', null) as pickup,
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
            'Y' as emergency,

            cast(null as string) as relationship_id,
            cast(null as string) as address,
            cast(null as string) as address2,
            cast(null as string) as city,
            cast(null as string) as state,
            cast(null as string) as zipcode,
            cast(null as string) as contact_gender,

            coalesce(
                a.emrg_2_relationship_ss, a.emrg_2_relationship_txt
            ) as student_relation,

            if(a.emrg_2_lives_with_yn, 'Y', null) as resides_with_stud,
            if(a.emrg_2_custody_yn, 'Y', null) as custody,
            if(a.emrg_2_pickup_yn, 'Y', null) as pickup,
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
            'Y' as emergency,

            cast(null as string) as relationship_id,
            cast(null as string) as address,
            cast(null as string) as address2,
            cast(null as string) as city,
            cast(null as string) as state,
            cast(null as string) as zipcode,
            cast(null as string) as contact_gender,

            coalesce(
                a.emrg_3_relationship_ss, a.emrg_3_relationship_txt
            ) as student_relation,

            if(a.emrg_3_lives_with_yn, 'Y', null) as resides_with_stud,
            if(a.emrg_3_custody_yn, 'Y', null) as custody,
            if(a.emrg_3_pickup_yn, 'Y', null) as pickup,
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
            'Y' as emergency,

            cast(null as string) as relationship_id,
            cast(null as string) as address,
            cast(null as string) as address2,
            cast(null as string) as city,
            cast(null as string) as state,
            cast(null as string) as zipcode,
            cast(null as string) as contact_gender,

            coalesce(
                a.emrg_4_relationship_ss, a.emrg_4_relationship_txt
            ) as student_relation,

            if(a.emrg_4_lives_with_yn, 'Y', null) as resides_with_stud,
            if(a.emrg_4_custody_yn, 'Y', null) as custody,
            if(a.emrg_4_pickup_yn, 'Y', null) as pickup,
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
            resides_with_stud,
            custody,
            emergency,
            pickup,
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
            resides_with_stud,
            custody,
            emergency,
            pickup,
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
        from crosswalked
    )

-- trunk-ignore(sqlfluff/ST06): column order fixed by Focus CONTACTS contract
select
    student_id,
    student_relation,
    sort_order,

    first_name,
    middle_name,
    last_name,

    resides_with_stud,
    custody,
    emergency,
    pickup,

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
from ranked

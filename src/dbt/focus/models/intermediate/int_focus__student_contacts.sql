with
    -- normalize the Y/null flags once; null is preserved as "unmaintained in
    -- Focus" (the Finalsite import seeds these as null; registrars set them)
    links as (
        select
            student_id,
            person_id,
            address_id,
            sort_order,

            student_relation as relationship,

            custody = 'Y' as is_custodial,
            emergency = 'Y' as is_emergency,
            pick_up = 'Y' as is_pickup,
            reunification = 'Y' as is_reunification,
        from {{ ref("stg_focus__students_join_people") }}
    ),

    people as (
        select
            person_id,
            first_name as contact_first_name,
            last_name as contact_last_name,
            email,

            nullif(array_to_string([first_name, last_name], ' '), '') as contact_name,
        from {{ ref("stg_focus__people") }}
    ),

    -- contact detail rows are free-typed by title; map to the phone-type
    -- vocabulary shared with the Finalsite contacts intermediate. Email-shaped
    -- titles (e.g. "Home Email") also match the home/work substrings below, so
    -- is_email_title is derived here and filtered out in phones_filtered
    -- rather than mistyped as phones. value is blank-normalized here so
    -- phones_ranked can filter the plain column. Unmapped and ambiguous
    -- (matching both vocabularies) titles are surfaced by the
    -- focus_unmapped_phone_contact_titles test.
    phones as (
        select
            person_id,
            detail_priority,

            nullif(trim(value), '') as `value`,
            regexp_contains(lower(title), r'e-?mail') as is_email_title,

            case
                when regexp_contains(lower(title), r'cell|mobile')
                then 'mobile'
                when regexp_contains(lower(title), r'home')
                then 'home'
                when regexp_contains(lower(title), r'work|business|office')
                then 'work'
                when regexp_contains(lower(title), r'day')
                then 'daytime'
            end as phone_type,
        from {{ ref("stg_focus__people_join_contacts") }}
    ),

    -- is_email_title is a plain boolean column here, not a function applied
    -- to a table column in WHERE.
    phones_filtered as (
        select person_id, detail_priority, value, phone_type,
        from phones
        where not is_email_title
    ),

    phones_ranked as (
        select
            person_id,
            value,
            phone_type,

            row_number() over (
                partition by person_id, phone_type
                order by detail_priority asc nulls last, value asc
            ) as type_rank,

            row_number() over (
                partition by person_id
                order by detail_priority asc nulls last, value asc
            ) as overall_rank,
        from phones_filtered
        where phone_type is not null and value is not null
    ),

    phones_typed as (
        select
            person_id,

            max(if(phone_type = 'mobile', value, null)) as phone_mobile,
            max(if(phone_type = 'home', value, null)) as phone_home,
            max(if(phone_type = 'work', value, null)) as phone_work,
            max(if(phone_type = 'daytime', value, null)) as phone_daytime,
        from phones_ranked
        where type_rank = 1
        group by person_id
    ),

    -- read off the unfiltered rank, not phones_typed's type_rank = 1 filter
    -- the overall_rank = 1 row can belong to a phone_type the type_rank filter
    -- has already discarded, so this must not read through that filter.
    primary_phone as (
        select person_id, value as phone_primary,
        from phones_ranked
        where overall_rank = 1
    ),

    addresses as (
        select
            address_id,

            nullif(
                array_to_string([address, address2, city, state, zipcode], ', '), ''
            ) as home_address,
        from {{ ref("stg_focus__address") }}
    ),

    -- one row per (student, address) the student resides at — residence = 'Y'
    -- only, matching the Finalsite lives_with_yn semantics is_household_member
    -- maps onto in Phase 2.
    -- grain projection: student_id, address_id are the partition key itself;
    -- not a mask for upstream duplicates
    student_addresses as (
        select distinct student_id, address_id,
        from {{ ref("stg_focus__students_join_address") }}
        where residence = 'Y'
    )

select
    l.student_id,
    l.person_id,
    l.relationship,
    l.sort_order,
    l.is_custodial,
    l.is_emergency,
    l.is_pickup,
    l.is_reunification,

    s.local_student_id,

    p.contact_name,
    p.contact_first_name,
    p.contact_last_name,
    p.email,

    a.home_address,

    {{ finalsite.clean_phone("pt.phone_mobile") }} as phone_mobile,
    {{ finalsite.clean_phone("pt.phone_home") }} as phone_home,
    {{ finalsite.clean_phone("pt.phone_work") }} as phone_work,
    {{ finalsite.clean_phone("pt.phone_daytime") }} as phone_daytime,
    {{ finalsite.clean_phone("pp.phone_primary") }} as phone_primary,

    if(l.address_id is null, null, sa.address_id is not null) as is_household_member,
from links as l
inner join {{ ref("stg_focus__students") }} as s on l.student_id = s.student_id
left join people as p on l.person_id = p.person_id
left join phones_typed as pt on l.person_id = pt.person_id
left join primary_phone as pp on l.person_id = pp.person_id
left join addresses as a on l.address_id = a.address_id
left join
    student_addresses as sa
    on l.student_id = sa.student_id
    and l.address_id = sa.address_id

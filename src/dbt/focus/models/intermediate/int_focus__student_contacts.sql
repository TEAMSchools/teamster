with
    -- one row per (person, phone_type) and one row per person overall, ranked
    -- by detail_priority then value. phone_type/is_email_title/value are
    -- already derived in staging; excludes rows that aren't a mapped,
    -- populated, non-email phone value.
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
        from {{ ref("stg_focus__people_join_contacts") }}
        where phone_type is not null and value is not null and not is_email_title
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
    l.student_relation as relationship,
    l.sort_order,
    l.is_custodial,
    l.is_emergency,
    l.is_pickup,
    l.is_reunification,

    s.local_student_id,

    p.contact_name,
    p.first_name as contact_first_name,
    p.last_name as contact_last_name,
    p.email,

    -- emitted raw, exactly as stored in Focus (native format for
    -- natively-entered numbers is (NNN) NNN-NNNN) -- this package has no
    -- dependency on the finalsite package, so E.164 normalization is deferred
    -- to the kipptaf consumer in Phase 2 rather than done here
    pt.phone_mobile,
    pt.phone_home,
    pt.phone_work,
    pt.phone_daytime,

    -- read off the unfiltered rank, not phones_typed's type_rank = 1 filter.
    -- the overall_rank = 1 row can belong to a phone_type that type_rank has
    -- already discarded, so this must not read through that filter. Two prior
    -- fix rounds exist because of this.
    pp.value as phone_primary,

    a.home_address,

    if(l.address_id is null, null, sa.address_id is not null) as is_household_member,
from {{ ref("stg_focus__students_join_people") }} as l
-- intentional scoping filter to students that exist in Focus; also supplies
-- local_student_id
inner join {{ ref("stg_focus__students") }} as s on l.student_id = s.student_id
left join {{ ref("stg_focus__people") }} as p on l.person_id = p.person_id
left join phones_typed as pt on l.person_id = pt.person_id
left join phones_ranked as pp on l.person_id = pp.person_id and pp.overall_rank = 1
left join {{ ref("stg_focus__address") }} as a on l.address_id = a.address_id
left join
    student_addresses as sa
    on l.student_id = sa.student_id
    and l.address_id = sa.address_id

select
    ar.contact_id,
    ar.contact_full_name as student_name,
    ar.ktc_cohort as hs_cohort,
    ar.ktc_status as `status`,
    ar.contact_currently_enrolled_school as currently_enrolled_school,
    ar.contact_owner_name,

    enr.account_type,
    enr.date_last_verified,
    enr.anticipated_graduation,
    enr.status as enrollment_status,

    acc.name as account_name,

    t.term_season as semester,
    t.term_verification_status as verification_status_src,

    left(t.year, 4) as `year`,

    coalesce(t.verified_by_advisor, t.verified_by_nsc) as verification_date,

    concat(upper(left(t.term_season, 2)), ' ', right(left(t.year, 4), 2)) as term,

    case
        when t.verified_by_advisor is not null
        then 'Verified by Counselor'
        when t.verified_by_nsc is not null
        then 'Verified by NSC'
        else 'Unverified'
    end as verification_status,

    row_number() over (
        partition by ar.contact_id, t.term_season, t.year
        order by t.term_verification_status desc
    ) as rn_term,
from {{ ref("int_kippadb__roster") }} as ar
inner join
    {{ ref("stg_kippadb__enrollment") }} as enr
    on ar.contact_id = enr.student
    and enr.status = 'Attending'
left join {{ ref("stg_kippadb__account") }} as acc on enr.school = acc.id
inner join
    {{ ref("stg_kippadb__term") }} as t
    on enr.id = t.enrollment
    and t.term_season != 'Summer'
where ar.contact_postsecondary_status is not null

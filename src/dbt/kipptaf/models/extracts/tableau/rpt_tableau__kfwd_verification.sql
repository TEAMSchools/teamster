select
    ar.contact_id,
    ar.contact_full_name as student_name,
    ar.ktc_cohort as hs_cohort,
    ar.ktc_status as status,
    ar.contact_currently_enrolled_school as currently_enrolled_school,
    ar.contact_owner_name,
    enr.ugrad_account_type,
    enr.ugrad_account_name,
    enr.ugrad_date_last_verified,
    enr.ugrad_anticipated_graduation,
    enr.ugrad_status,
    t.term_season as semester,
    left(t.year, 4) as year,
    concat(upper(left(t.term_season, 2)), ' ', right(left(t.year, 4), 2)) as term,
    case
        when t.verified_by_advisor is not null
        then 'Verified by Counselor'
        when t.verified_by_nsc is not null
        then 'Verified by NSC'
        else 'Unverified'
    end as verification_status,
    t.term_verification_status as verification_status_src,
    coalesce(t.verified_by_advisor, t.verified_by_nsc) as verification_date,
    row_number() over (
        partition by ar.contact_id, t.term_season, t.year
        order by t.term_verification_status desc
    ) as rn_term,
from {{ ref("int_kippadb__roster") }} as ar
inner join
    {{ ref("int_kippadb__enrollment_pivot") }} as enr
    on (
        ar.contact_id = enr.student
        and enr.ugrad_account_name is not null
        and enr.ugrad_status != 'Matriculated'
    )
inner join
    {{ ref("stg_kippadb__term") }} as t
    on (enr.ugrad_enrollment_id = t.enrollment and t.term_season != 'Summer')

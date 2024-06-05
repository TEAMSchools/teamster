select
    e1.student as sf_contact_id,
    e1.pursuing_degree_type,

    e1.id as enrollment_1_id,
    e1.name as enrollment_1_name,
    e1.type as enrollment_1_type,
    e1.start_date as enrollment_1_start_date,
    e1.actual_end_date as enrollment_1_actual_end_date,
    e1.status as enrollment_1_status,
    e1.date_last_verified as enrollment_1_date_last_verified,
    e1.nsc_verified as enrollment_1_nsc_verified,

    e2.id as enrollment_2_id,
    e2.name as enrollment_2_name,
    e2.start_date as enrollment_2_start_date,
    e2.actual_end_date as enrollment_2_actual_end_date,
    e2.status as enrollment_2_status,
    e2.date_last_verified as enrollment_2_date_last_verified,
    e2.nsc_verified as enrollment_2_nsc_verified,

    r.ktc_cohort as cohort,
    r.contact_owner_name,
    r.contact_advising_provider,
from {{ ref("stg_kippadb__enrollment") }} as e1
inner join
    {{ ref("stg_kippadb__enrollment") }} as e2
    on e1.student = e2.student
    and e1.pursuing_degree_type = e2.pursuing_degree_type
    and e1.id != e2.id
    and e2.status != 'Did Not Enroll'
    and (
        e2.start_date
        between e1.start_date and coalesce(e1.actual_end_date, date('9999-12-31'))
        or coalesce(e2.actual_end_date, '9999-12-31')
        between e1.start_date and coalesce(e1.actual_end_date, date('9999-12-31'))
    )
inner join {{ ref("int_kippadb__roster") }} as r on e1.student = r.contact_id
where e1.status != 'Did Not Enroll'

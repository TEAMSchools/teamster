with
    roster_scaffold as (
        select
            r.student_number,
            r.contact_id,
            r.ktc_cohort,

            n as persistence_year,

            r.ktc_cohort + n as academic_year,
            date(r.ktc_cohort + n, 10, 31) as persistence_date_fall,
            date(r.ktc_cohort + n + 1, 3, 31) as persistence_date_spring,
        from {{ ref("int_kippadb__roster") }} as r
        cross join unnest([0, 1, 2, 3, 4, 5]) as n
    )

select
    r.student_number,
    r.contact_id as sf_contact_id,
    r.ktc_cohort,
    r.academic_year,
    r.persistence_year,

    e.id as enrollment_id,
    e.pursuing_degree_type as pursuing_degree_type,
    e.status as enrollment_status,
    e.start_date as start_date,
    e.actual_end_date as actual_end_date,

    a.name as account_name,
    a.type as account_type,

    eis.hs_account_name,
    eis.ecc_pursuing_degree_type,

    'Fall' as semester,

    if(
        eis.ecc_pursuing_degree_type in ("Bachelor's (4-year)", "Associate's (2 year)"),
        true,
        false
    ) as is_ecc,

    if(eis.ecc_pursuing_degree_type = "Bachelor's (4-year)", true, false) as is_ecc_ba,
    if(eis.ecc_pursuing_degree_type = "Associate's (2 year)", true, false) as is_ecc_aa,

    if(r.academic_year = r.ktc_cohort + 1, true, false) as is_first_year,

    case
        when r.persistence_date_fall > current_date('{{ var("local_timezone") }}')
        then null
        when e.actual_end_date >= r.persistence_date_fall
        then 1
        when e.actual_end_date < r.persistence_date_fall and e.status = 'Graduated'
        then 1
        when
            e.actual_end_date is null and eis.ugrad_status in ('Graduated', 'Attending')
        then 1
        else 0
    end as is_persisting_int,

    case
        when r.persistence_date_fall > current_date('{{ var("local_timezone") }}')
        then null
        when
            e.actual_end_date >= r.persistence_date_fall
            and eis.ecc_account_id = e.school
        then 1
        when
            e.actual_end_date < r.persistence_date_fall
            and e.status = 'Graduated'
            and eis.ecc_account_id = e.school
        then 1
        when
            e.actual_end_date is null
            and eis.ugrad_status in ('Graduated', 'Attending')
            and eis.ecc_account_id = e.school
        then 1
        else 0
    end as is_retained_int,

    case
        when r.persistence_date_fall > current_date('America/New_York')
        then null
        when
            e.actual_end_date >= r.persistence_date_fall
            and eis.ecc_account_id = e.school
        then 'Retained'
        when e.actual_end_date >= r.persistence_date_fall
        then 'Persisted'
        when e.actual_end_date < r.persistence_date_fall and e.status = 'Graduated'
        then 'Graduated'
        when e.actual_end_date is null and eis.ugrad_status = 'Graduated'
        then 'Graduated'
        when
            e.actual_end_date is null
            and eis.ugrad_status = 'Attending'
            and eis.ecc_account_id = e.school
        then 'Retained'
        when e.actual_end_date is null and eis.ugrad_status = 'Attending'
        then 'Persisted'
        else 'Did not persist'
    end as persistence_status,

    row_number() over (
        partition by r.student_number, r.academic_year order by e.start_date desc
    ) as rn_enrollment_year,

from roster_scaffold as r
left join
    {{ ref("stg_kippadb__enrollment") }} as e
    on r.contact_id = e.student
    and r.persistence_date_fall between e.start_date and coalesce(
        e.actual_end_date, date(({{ var("current_academic_year") }} + 1), 6, 30)
    )
    and e.pursuing_degree_type in ("Bachelor's (4-year)", "Associate's (2 year)")
    and e.status not in ('Did Not Enroll', 'Deferred')
left join {{ ref("stg_kippadb__account") }} as a on e.school = a.id
left join
    {{ ref("int_kippadb__enrollment_pivot") }} as eis on r.contact_id = eis.student

union all

select
    r.student_number,
    r.contact_id as sf_contact_id,
    r.ktc_cohort,
    r.academic_year,
    r.persistence_year,

    e.id as enrollment_id,
    e.pursuing_degree_type as pursuing_degree_type,
    e.status as enrollment_status,
    e.start_date as start_date,
    e.actual_end_date as actual_end_date,

    a.name as account_name,
    a.type as account_type,

    eis.hs_account_name,
    eis.ecc_pursuing_degree_type,

    'Spring' as semester,

    if(
        eis.ecc_pursuing_degree_type in ("Bachelor's (4-year)", "Associate's (2 year)"),
        true,
        false
    ) as is_ecc,
    if(eis.ecc_pursuing_degree_type = "Bachelor's (4-year)", true, false) as is_ecc_ba,
    if(eis.ecc_pursuing_degree_type = "Associate's (2 year)", true, false) as is_ecc_aa,

    if(r.academic_year = r.ktc_cohort + 1, true, false) as is_first_year,

    case
        when r.persistence_date_spring > current_date('{{ var("local_timezone") }}')
        then null
        when e.actual_end_date >= r.persistence_date_spring
        then 1
        when e.actual_end_date < r.persistence_date_spring and e.status = 'Graduated'
        then 1
        when
            e.actual_end_date is null and eis.ugrad_status in ('Graduated', 'Attending')
        then 1
        else 0
    end as is_persisting_int,

    case
        when r.persistence_date_spring > current_date('{{ var("local_timezone") }}')
        then null
        when
            e.actual_end_date >= r.persistence_date_spring
            and eis.ecc_account_id = e.school
        then 1
        when
            e.actual_end_date < r.persistence_date_spring
            and e.status = 'Graduated'
            and eis.ecc_account_id = e.school
        then 1
        when
            e.actual_end_date is null
            and eis.ugrad_status in ('Graduated', 'Attending')
            and eis.ecc_account_id = e.school
        then 1
        else 0
    end as is_retained_int,

    case
        when r.persistence_date_spring > current_date('America/New_York')
        then null
        when
            e.actual_end_date >= r.persistence_date_spring
            and eis.ecc_account_id = e.school
        then 'Retained'
        when e.actual_end_date >= r.persistence_date_spring
        then 'Persisted'
        when e.actual_end_date < r.persistence_date_spring and e.status = 'Graduated'
        then 'Graduated'
        when e.actual_end_date is null and eis.ugrad_status = 'Graduated'
        then 'Graduated'
        when
            e.actual_end_date is null
            and eis.ugrad_status = 'Attending'
            and eis.ecc_account_id = e.school
        then 'Retained'
        when e.actual_end_date is null and eis.ugrad_status = 'Attending'
        then 'Persisted'
        else 'Did not persist'
    end as persistence_status,

    row_number() over (
        partition by r.student_number, r.academic_year order by e.start_date desc
    ) as rn_enrollment_year,

from roster_scaffold as r
left join
    {{ ref("stg_kippadb__enrollment") }} as e
    on r.contact_id = e.student
    and r.persistence_date_spring between e.start_date and coalesce(
        e.actual_end_date, date(({{ var("current_academic_year") }} + 1), 6, 30)
    )
    and e.pursuing_degree_type in ("Bachelor's (4-year)", "Associate's (2 year)")
    and e.status not in ('Did Not Enroll', 'Deferred')
left join {{ ref("stg_kippadb__account") }} as a on e.school = a.id
left join
    {{ ref("int_kippadb__enrollment_pivot") }} as eis on r.contact_id = eis.student

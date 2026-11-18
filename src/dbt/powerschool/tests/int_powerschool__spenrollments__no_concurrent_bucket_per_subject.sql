with
    buckets as (
        select
            sp.dcid,
            sp.studentid,
            sp.academic_year,
            sp.specprog_name,
            sp.enter_date,

            ssp.schoolid,

            coalesce(sp.exit_date, '9999-12-31') as exit_date,

            trim(split(sp.specprog_name, '-')[safe_offset(1)]) as subject,
        from {{ ref("int_powerschool__spenrollments") }} as sp
        inner join
            {{ ref("stg_powerschool__spenrollments") }} as ssp on sp.dcid = ssp.dcid
        where sp.specprog_name like 'Bucket%'
    )

select
    a.studentid,
    a.academic_year,
    a.subject,
    a.schoolid,
    a.specprog_name as specprog_name_a,
    a.enter_date as enter_date_a,
    b.specprog_name as specprog_name_b,
    b.enter_date as enter_date_b,
from buckets as a
inner join
    buckets as b
    on a.studentid = b.studentid
    and a.academic_year = b.academic_year
    and a.subject = b.subject
    and a.specprog_name < b.specprog_name
    -- a shared enter date counts even when 1 record's exit precedes its enter
    and (
        a.enter_date = b.enter_date
        or (a.enter_date < b.exit_date and a.exit_date > b.enter_date)
    )

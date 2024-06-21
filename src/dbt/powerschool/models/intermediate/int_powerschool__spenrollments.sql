select
    sp.dcid,
    sp.id,
    sp.studentid,
    sp.programid,
    sp.gradelevel,
    sp.sp_comment,
    sp.enter_date,
    sp.exit_date,
    sp.exitcode,
    sp.academic_year,

    gen.name as specprog_name,
from {{ ref("stg_powerschool__spenrollments") }} as sp
inner join
    {{ ref("stg_powerschool__gen") }} as gen
    on sp.programid = gen.id
    and gen.cat = 'specprog'

{%- set self_contained_specprog_names = [
    "Self-Contained Special Education",
    "Pathways ES",
    "Pathways MS",
] -%}

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

    if(gen.name = 'Out of District', true, false) as is_out_of_district,
    if(
        gen.name in unnest({{ self_contained_specprog_names }}), true, false
    ) as is_self_contained,
from {{ ref("stg_powerschool__spenrollments") }} as sp
inner join
    {{ ref("stg_powerschool__gen") }} as gen
    on sp.programid = gen.id
    and gen.cat = 'specprog'

with
    -- Neither field has a usable Focus source. Focus ese_fefp_code is an FEFP
    -- funding code covering 162 of 419 archive SPED students, and
    -- english_language_learner_pk_12 puts 98% of students at the
    -- not-applicable code. Carry the archive value forward for returning
    -- students; new students get null, because a false negative on IEP status
    -- is compliance-adjacent and unknown must read as unknown.
    --
    -- The archive keys these on studentsdcid, so resolve to student_number
    -- here. dcid is PowerSchool plumbing and stops at this layer.
    archive as (
        select s.student_number, scf.spedlep, scf.lep_status,
        from {{ ref("stg_powerschool__students") }} as s
        inner join
            {{ ref("stg_powerschool__studentcorefields") }} as scf
            on s.dcid = scf.studentsdcid
            and s._dbt_source_project = scf._dbt_source_project
        where s._dbt_source_project = 'kippmiami'
    )

select
    c._dbt_source_relation,
    c._dbt_source_project,
    c.student_number,

    a.spedlep,
    a.lep_status,
from {{ ref("int_focus__students_conformed") }} as c
left join archive as a on c.student_number = a.student_number

with
    -- The staging model carries only studentsdcid, so resolve it to
    -- student_number here. dcid is PowerSchool plumbing and stops at this
    -- layer; the mart joins on student_number.
    powerschool as (
        select
            scf._dbt_source_relation,
            scf._dbt_source_project,
            scf.spedlep,
            scf.lep_status,

            s.student_number,
        from {{ ref("stg_powerschool__studentcorefields") }} as scf
        inner join
            {{ ref("stg_powerschool__students") }} as s
            on scf.studentsdcid = s.dcid
            and scf._dbt_source_project = s._dbt_source_project
        -- Miami's archive is superseded by the Focus branch below.
        where s._dbt_source_project != 'kippmiami'
    )

select _dbt_source_relation, _dbt_source_project, student_number, spedlep, lep_status,
from powerschool

union all

select _dbt_source_relation, _dbt_source_project, student_number, spedlep, lep_status,
from {{ ref("int_focus__student_core_fields_conformed") }}

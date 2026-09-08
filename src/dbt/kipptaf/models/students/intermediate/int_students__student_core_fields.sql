with
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
        where s._dbt_source_project != 'kippmiami'
    ),

    -- Both fields are conformed in int_focus__students. Neither is fully
    -- populated in Focus today, and that is deliberate: an unpopulated Focus
    -- field reads as unknown, which is a visible prompt for Ops, where
    -- carrying the frozen archive forward silently froze Miami's IEP and ELL
    -- status at its 2025 values.
    focus_conformed as (
        select
            _dbt_source_relation,
            _dbt_source_project,
            student_number,
            spedlep,
            lep_status,
        from {{ ref("int_focus__students") }}
    )

select _dbt_source_relation, _dbt_source_project, student_number, spedlep, lep_status,
from powerschool

union all

select _dbt_source_relation, _dbt_source_project, student_number, spedlep, lep_status,
from focus_conformed

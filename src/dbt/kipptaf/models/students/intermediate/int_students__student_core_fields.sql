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
    ),

    -- Neither field has a usable Focus source, for different reasons.
    --
    -- spedlep: ese_fefp_code is an FEFP funding-matrix code, not an IEP flag,
    -- and only applies to higher-cost placements -- it covers 149 of the 419
    -- archive SPED students. The fields that would be right (ESE, IEP,
    -- Disability, ESE Exceptionalities, Frontline IEP) are defined in the
    -- Focus catalog but carry no data: the column-backed ones are 0% populated
    -- and the log-backed ones have zero rows in custom_field_log_entries,
    -- which holds 27k rows for other fields.
    --
    -- lep_status: english_language_learner_pk_12 IS populated (3,837 of 3,964)
    -- with the right FLDOE code set, but 3,819 of those sit at the default
    -- "Not applicable [ZZ]" option, including 211 students the archive flags
    -- as LEP. Only 18 carry a real code. Reading it would overwrite real LEP
    -- status with a default, so it is an Ops data-entry gap rather than a
    -- missing source -- see TODO below.
    --
    -- Both are worth revisiting once Ops populates them in Focus. Carry the
    -- archive value forward meanwhile; new students get null, because a false
    -- negative on IEP status is compliance-adjacent and unknown must read as
    -- unknown.
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
    ),

    -- The unprefixed Focus student id is the canonical network student number.
    -- Same unprefix rule int_students__students applies to the Focus branch of
    -- the student spine.
    focus_identified as (
        select
            _dbt_source_relation,
            _dbt_source_project,

            {{ unprefix_focus_student_id("student_id") }} as student_number,
        from {{ ref("int_focus__students") }}
    ),

    focus_conformed as (
        select
            i._dbt_source_relation,
            i._dbt_source_project,
            i.student_number,

            a.spedlep,
            a.lep_status,
        from focus_identified as i
        left join archive as a on i.student_number = a.student_number
    )

select _dbt_source_relation, _dbt_source_project, student_number, spedlep, lep_status,
from powerschool

union all

select _dbt_source_relation, _dbt_source_project, student_number, spedlep, lep_status,
from focus_conformed

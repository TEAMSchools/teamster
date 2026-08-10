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

    -- Both fields read straight from Focus. Neither is fully populated there
    -- today, and that is deliberate: an unpopulated Focus field reads as
    -- unknown, which is a visible prompt for Ops to fill it in, where carrying
    -- the frozen archive forward silently froze Miami's IEP and ELL status at
    -- its 2025 values and would have drifted further every year.
    --
    -- ese_fefp_code is the only ESE field Focus stores -- ESE, IEP,
    -- Disability, ESE Exceptionalities and Frontline IEP are all defined in
    -- the catalog but hold no data. It is an FEFP funding-matrix code, so it
    -- names 162 students against the archive's 419. Any code means the
    -- student receives ESE services; its absence does not mean the student
    -- has no IEP, so it maps to null, not 'No IEP'.
    --
    -- english_language_learner_pk_12 carries the FLDOE code set. LY is
    -- currently LEP; LF, LA, LZ and the ZZ variants are not. LP and TT mean
    -- tested-or-pending, which is genuinely unknown rather than false. 3,819
    -- of 3,964 students currently sit at the "Not applicable" default,
    -- including 211 the archive flagged as LEP -- Ops closing that gap is the
    -- point of reading the field rather than the archive.
    focus_conformed as (
        select
            _dbt_source_relation,
            _dbt_source_project,

            {{ unprefix_focus_student_id("student_id") }} as student_number,

            if(ese_fefp_code_label is not null, 'SPED', null) as spedlep,

            case
                regexp_extract(english_language_learner_pk_12_label, r'\[(\w+)\]')
                when 'LY'
                then true
                when 'LF'
                then false
                when 'LA'
                then false
                when 'LZ'
                then false
                when 'TZ'
                then false
                when 'ZZ'
                then false
            end as lep_status,
        from {{ ref("int_focus__students") }}
    )

select _dbt_source_relation, _dbt_source_project, student_number, spedlep, lep_status,
from powerschool

union all

select _dbt_source_relation, _dbt_source_project, student_number, spedlep, lep_status,
from focus_conformed

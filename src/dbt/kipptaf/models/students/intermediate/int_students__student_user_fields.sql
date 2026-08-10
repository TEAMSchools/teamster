with
    -- The staging model carries only studentsdcid, so resolve it to
    -- student_number here. dcid is PowerSchool plumbing and stops at this
    -- layer; the mart joins on student_number.
    powerschool as (
        select
            suf._dbt_source_relation,
            suf._dbt_source_project,
            suf.fleid,
            suf.gifted_and_talented,

            s.student_number,
        from {{ ref("stg_powerschool__u_studentsuserfields") }} as suf
        inner join
            {{ ref("stg_powerschool__students") }} as s
            on suf.studentsdcid = s.dcid
            and suf._dbt_source_project = s._dbt_source_project
        -- Miami's archive is superseded by the Focus branch below.
        where s._dbt_source_project != 'kippmiami'
    ),

    -- Gifted reads from Focus's Gifted Eligibility field, the only one it
    -- stores -- "Gifted (Computed)" is a computed-type field Focus never
    -- persists. Eligibility is recorded as the FLDOE criteria paragraph the
    -- student qualified under, so any A or B is gifted and Z is not. It names
    -- 15 students against the archive's 34, which is the gap for Ops to close.
    focus_conformed as (
        select
            _dbt_source_relation,
            _dbt_source_project,
            florida_education_identifier as fleid,

            {{ unprefix_focus_student_id("student_id") }} as student_number,

            case
                when gifted_eligibility_label like 'Student was determined eligible%'
                then 'Y'
                when gifted_eligibility_label is not null
                then 'N'
            end as gifted_and_talented,
        from {{ ref("int_focus__students") }}
    )

select
    _dbt_source_relation,
    _dbt_source_project,
    student_number,
    fleid,
    gifted_and_talented,
from powerschool

union all

select
    _dbt_source_relation,
    _dbt_source_project,
    student_number,
    fleid,
    gifted_and_talented,
from focus_conformed

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

    -- fleid and gifted_and_talented are both conformed in
    -- int_focus__students; Focus's Gifted Eligibility names 15 students
    -- against the frozen archive's 34, a gap for Ops to close.
    focus_conformed as (
        select
            _dbt_source_relation,
            _dbt_source_project,
            student_number,
            gifted_and_talented,

            florida_education_identifier as fleid,
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

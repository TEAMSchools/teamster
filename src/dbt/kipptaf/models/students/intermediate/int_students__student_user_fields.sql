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

    -- The archive's user fields are keyed on studentsdcid, so resolve to
    -- student_number here. dcid is PowerSchool plumbing and stops at this
    -- layer; the mart joins on student_number.
    archive as (
        select s.student_number, suf.gifted_and_talented,
        from {{ ref("stg_powerschool__students") }} as s
        inner join
            {{ ref("stg_powerschool__u_studentsuserfields") }} as suf
            on s.dcid = suf.studentsdcid
            and s._dbt_source_project = suf._dbt_source_project
        where s._dbt_source_project = 'kippmiami'
    ),

    -- The unprefixed Focus student id is the canonical network student number.
    -- Same unprefix rule int_students__students applies to the Focus branch of
    -- the student spine.
    focus_identified as (
        select
            _dbt_source_relation,
            _dbt_source_project,
            florida_education_identifier as fleid,

            cast(
                regexp_replace(cast(student_id as string), r'^8400', '') as int64
            ) as student_number,
        from {{ ref("int_focus__students") }}
    ),

    -- Gifted status carries forward from the frozen PowerSchool archive for
    -- returning students, because the Focus Gifted (Computed) custom field is
    -- effectively unpopulated.
    focus_conformed as (
        select
            i._dbt_source_relation,
            i._dbt_source_project,
            i.student_number,
            i.fleid,

            a.gifted_and_talented,
        from focus_identified as i
        left join archive as a on i.student_number = a.student_number
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

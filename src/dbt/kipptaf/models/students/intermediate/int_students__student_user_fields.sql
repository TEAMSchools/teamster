with
    powerschool as (
        select
            suf._dbt_source_relation,
            suf._dbt_source_project,

            s.student_number,

            cast(null as string) as fleid,
            cast(null as string) as gifted_and_talented,
        from {{ ref("stg_powerschool__u_studentsuserfields") }} as suf
        inner join
            {{ ref("stg_powerschool__students") }} as s
            on suf.studentsdcid = s.dcid
            and suf._dbt_source_project = s._dbt_source_project
    ),

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

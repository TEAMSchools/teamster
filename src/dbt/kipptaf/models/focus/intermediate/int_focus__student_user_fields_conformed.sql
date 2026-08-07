with
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
    )

select
    c._dbt_source_relation,
    c._dbt_source_project,
    c.student_number,
    c.florida_education_identifier as fleid,

    a.gifted_and_talented,
from {{ ref("int_focus__students_conformed") }} as c
left join archive as a on c.student_number = a.student_number

with
    stored_grades as (
        select
            studentid,
            course_number,
            _dbt_source_project,

            cast(dcid as string) as dcid,
            cast(academic_year + 1 as string) as school_year_id,
            cast(percent as string) as `grade`,
        from {{ ref("stg_powerschool__storedgrades") }}
        where
            _dbt_source_project in ('kippnewark', 'kippcamden', 'kipppaterson')
            and academic_year = {{ var("current_academic_year") }}
            and storecode in ('Q1', 'Q2', 'Q3', 'Q4')
            -- grade is required by the vendor; a stored grade with no percent
            -- is unusable
            and percent is not null
    )

select
    sg.school_year_id,
    sg.grade,

    cast(s.student_number as string) as student_id,

    concat(sg._dbt_source_project, '-', sg.dcid) as record_id,
    concat(sg._dbt_source_project, '-', sg.course_number) as course_id,
from stored_grades as sg
inner join
    {{ ref("stg_powerschool__students") }} as s
    on sg.studentid = s.id
    and sg._dbt_source_project = s._dbt_source_project
